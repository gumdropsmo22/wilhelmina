from datetime import date, datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cogs.chat import Chat
from cogs.rules import RulesAdmin
from services import coven_registry, memory_admin, memory_extraction, memory_ledger, member_profiles
from services import eight_ball, help as help_service, memory_extraction_provider
from services.chat_continuity import ConversationKey
from services.database import initialize_database, managed_connection
from cogs.memory_extraction import MemoryExtraction
from utils.embeds import system_embed


@pytest.fixture
def dbpath(tmp_path):
    path = tmp_path / 'test.sqlite3'
    initialize_database(path)
    with managed_connection(path) as db:
        coven_registry.bootstrap_registry(db, guild_id=100, wilhelmina_user_id=999,
            founder_user_id=2, founder_name='Founder', actor_user_id=2)
        member_profiles.save_member_identity(db, guild_id=100, user_id=2,
            discord_display_name='Founder', preferred_name='Founder', birth_date='1990-01-01',
            today=date(2026,10,26), actor_user_id=2)
    return path


def add(db, summary, topic):
    return memory_ledger.add_memory(db, guild_id=100, subject_user_id=2,
        category='Preference', epistemic_label='Fact', summary=summary,
        topic_key=topic, actor_user_id=2)


def test_unicode_and_natural_query(dbpath):
    with managed_connection(dbpath) as db:
        first=add(db,'أفضل القهوة','drink')
        second=add(db,'أحب الكتب','books')
        assert first.memory.id != second.memory.id
        assert memory_ledger.search_memories(db,guild_id=100,query='القهوة')
        add(db,'Prefers coffee','coffee')
        assert memory_ledger.search_memories(db,guild_id=100,query='Who else likes coffee?')
        assert add(db,'أفضل القهوة','drink').memory.id == first.memory.id


def test_existing_unicode_keys_migrate_without_losing_receipts(dbpath):
    with managed_connection(dbpath) as db:
        result=add(db,'أفضل القهوة','drink')
        db.execute('DELETE FROM schema_migrations WHERE version=13')
        db.execute("UPDATE memory_records SET normalized_key='legacy-ascii-key'")
        memory_ledger.initialize_memory_schema(db)
        assert memory_ledger.get_memory(db,result.memory.id).normalized_key == memory_ledger.normalize_memory_key('Preference','أفضل القهوة')
        assert len(memory_ledger.list_receipts(db,result.memory.id)) == 1
        memory_ledger.initialize_memory_schema(db)
        assert len(memory_ledger.list_profile(db,guild_id=100,subject_user_id=2)) == 1


@pytest.mark.asyncio
async def test_purge_revokes_inflight_provider_result(dbpath,monkeypatch):
    import asyncio
    with managed_connection(dbpath) as db:
        add(db,'Likes clocks','clocks')
        job=memory_extraction.enqueue_message(db,guild_id=100,subject_user_id=2,
            source_context='dm',author_user_id=2,channel_id=None,message_id=500,
            jump_url=None,content='I like clocks',source_created_at=datetime.now(UTC).isoformat())
    cog=object.__new__(MemoryExtraction)
    cog.bot=SimpleNamespace(user=SimpleNamespace(id=999),settings=SimpleNamespace(home_guild_id=100,database_path=dbpath))
    started,release=asyncio.Event(),asyncio.Event()
    async def provider(**kwargs):
        started.set(); await release.wait()
        return SimpleNamespace(payload={'candidates':[dict(category='Preference',epistemic_label='Fact',claim_subject='author',claim_attribution='self',summary='Likes clocks',topic_key='clocks',importance=50,confidence=95,entities=[])]})
    monkeypatch.setenv('MEMORY_COLLECTION_MODE','interaction')
    monkeypatch.setattr(memory_extraction_provider,'provider_ready',lambda:True)
    monkeypatch.setattr(memory_extraction_provider,'extract_structured',provider)
    task=asyncio.create_task(MemoryExtraction.worker.coro(cog))
    await asyncio.wait_for(started.wait(),5)
    with managed_connection(dbpath) as db:
        memory_admin.delete_member_data(db,guild_id=100,subject_user_id=2,actor_user_id=2)
        assert memory_extraction.get_job(db,job.id).claim_token is None
    release.set();await asyncio.wait_for(task,5)
    with managed_connection(dbpath) as db:
        assert not memory_ledger.list_profile(db,guild_id=100,subject_user_id=2)
        assert memory_extraction.get_job(db,job.id).content is None


@pytest.mark.asyncio
async def test_rules_admin_rejects_non_manager():
    cog=RulesAdmin(SimpleNamespace(settings=SimpleNamespace(home_guild_id=100)))
    interaction=SimpleNamespace(user=SimpleNamespace(guild_permissions=SimpleNamespace(manage_guild=False)),guild_id=100,response=SimpleNamespace(send_message=AsyncMock()))
    assert not await cog._guard(interaction)


@pytest.mark.asyncio
async def test_bulk_delete_tombstones_inflight_and_removes_history():
    cog=Chat(SimpleNamespace(settings=SimpleNamespace(home_guild_id=100)))
    key=ConversationKey('guild',100,10)
    cog.runtime.record_exchange(key,source_message_id=500,author_user_id=2,user_text='hello',assistant_text='reply')
    await cog.on_raw_bulk_message_delete(SimpleNamespace(guild_id=100,message_ids={500,501}))
    assert not cog.runtime.history(key)
    assert cog.runtime.source_text_for_record(501,'inflight') is None


@pytest.mark.parametrize('root',['admin','rules-admin','memory-admin','identity-admin','registry-admin','broadcast-admin'])
def test_private_roots_hidden(root):
    assert not help_service.is_public_command(SimpleNamespace(name='status',parent=SimpleNamespace(name=root,parent=None),extras={}))


def test_icons_and_credential_topics():
    embed=system_embed(description='test').to_dict()
    assert 'icon_url' not in embed['author'] and 'icon_url' not in embed['footer']
    for text in ['I use a password manager','I prefer credit card rewards']:
        assert memory_extraction.guard_extractable_text(text) == text
    with pytest.raises(memory_ledger.BlockedMemoryContent):
        memory_extraction.guard_extractable_text('password: real-secret-value')


@pytest.mark.asyncio
async def test_eight_ball_voice_and_bound(monkeypatch):
    async def generate(prompt):
        assert 'not a' in prompt and 'mother' in prompt
        return 'x'*5000
    monkeypatch.setattr(eight_ball,'generate_text_async',generate)
    assert len(await eight_ball.generate_answer('yes')) <= 600
