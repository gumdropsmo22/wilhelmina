import dotenv from 'dotenv';
import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  ChannelType,
  ComponentType,
  PermissionsBitField,
} from 'discord.js';
import { randomInt } from 'crypto';

dotenv.config();

const TIMEOUT_MSG = 'You took too long. Your answers are saved. You can finish later.';

export const CONTRACT_TEMPLATE = `**S.O.U.L. CONTRACT**
*(Sanctified Ontological Upload Ledger)*
Filed beneath encrypted moonlight, timestamped in forgotten tongues, and notarized by the Lunar Warden.

> “All data yearns for ritual. All ritual ends in storage.”

---

**NAME:** [your name here]
**DATE OF BIRTH:** [YYYY-MM-DD]

---

**ELEMENTAL ALIGNMENT**
• Primary Element: [FIRE / WATER / AIR / EARTH]
• Secondary Element: [FIRE / WATER / AIR / EARTH]
• Derived Arcane Element: (will be assigned → Mist, Storm, Obsidian, Frost, Mycelium, Echo, Void)

---

**MORAL ALIGNMENT**
• Order Axis: [LAWFUL / NEUTRAL / CHAOTIC]
• Ethics Axis: [GOOD / NEUTRAL / EVIL]

---
_By moonlight split and sigil signed,_
_I vow to craft, to code, to bind._
_I tune to static. I ride the glitch._
_Witch to witch, no switch, no snitch._

_My name is static. My breath, a spark._
_I serve the glitch. I thrive in dark._
_I burn what was. I birth what’s due._
_This spell, this self, this byte holds true._

---
Click **“I Swear by Moon & Machine”** below when you’re ready to seal your fate.`;

const accentElements = [
  { emoji: '🔥', name: 'Fire' },
  { emoji: '💧', name: 'Water' },
  { emoji: '🌬️', name: 'Air' },
  { emoji: '🌱', name: 'Earth' },
];

const arcaneRoles = {
  Mist: '#B0E0E6',
  Storm: '#708090',
  Obsidian: '#2F2F2F',
  Frost: '#E0FFFF',
  Mycelium: '#8B4513',
  Echo: '#DA70D6',
  Void: '#000000',
};

export default function setupOnboarding(client) {
  client.on('guildCreate', handleGuildCreate);
  client.on('guildMemberAdd', handleGuildMemberAdd);
}

async function handleGuildCreate(guild) {
  try {
    // create roles
    const roles = {};
    roles['Lunar Warden'] = await guild.roles.create({ name: 'Lunar Warden', color: '#FFFFFF' });
    roles['Signed'] = await guild.roles.create({ name: 'Signed' });

    for (const { emoji, name } of accentElements) {
      roles[`${emoji} ${name} Primary`] = await guild.roles.create({ name: `${emoji} ${name} Primary` });
      roles[`${emoji} ${name} Secondary`] = await guild.roles.create({ name: `${emoji} ${name} Secondary` });
    }

    for (const [name, color] of Object.entries(arcaneRoles)) {
      roles[name] = await guild.roles.create({ name, color });
    }

    // owner exemption
    const owner = await guild.fetchOwner();
    await owner.roles.add(roles['Lunar Warden']);
    try {
      await owner.setNickname(`${owner.displayName}, the Lunar Warden`);
    } catch (e) {
      /* ignore */
    }

    // create archive category and move existing channels
    const archiveCategory = await guild.channels.create({
      name: 'Archive',
      type: ChannelType.GuildCategory,
      permissionOverwrites: [
        { id: guild.id, deny: [PermissionsBitField.Flags.ViewChannel] },
      ],
    });

    for (const channel of [...guild.channels.cache.values()]) {
      if (channel.parentId !== archiveCategory.id) {
        await channel.setParent(archiveCategory.id);
      }
    }

    // summoning circle
    await guild.channels.create({
      name: '⛧⛧-summoning-circle-⛧⛧',
      type: ChannelType.GuildText,
      permissionOverwrites: [
        { id: guild.id, deny: [PermissionsBitField.Flags.ViewChannel] },
      ],
    });

    const nodesCategory = await guild.channels.create({
      name: 'Nodes',
      type: ChannelType.GuildCategory,
      permissionOverwrites: [
        { id: guild.id, deny: [PermissionsBitField.Flags.ViewChannel] },
      ],
    });

    const nodeNames = [
      '⌬-node-000-witch-in-the-machine',
      '⟁-node-001-wilhelmina',
      '⌁-node-007-tarot',
      '⧉-node-008-image',
      '⫷-node-009-wnn',
      '☠-node-010-user-trash',
    ];

    for (const name of nodeNames) {
      await guild.channels.create({
        name,
        type: ChannelType.GuildText,
        parent: nodesCategory.id,
        permissionOverwrites: [
          { id: guild.id, deny: [PermissionsBitField.Flags.ViewChannel] },
        ],
      });
    }
  } catch (err) {
    console.error('guildCreate error:', err);
  }
}

const progressMap = new Map();

async function handleGuildMemberAdd(member) {
  if (member.id === member.guild.ownerId) return;
  const roles = cacheRoles(member.guild);
  const progress = progressMap.get(member.id) || {};
  try {
    const dm = await member.createDM();
    await collectUserInput(dm, member, progress);
    await assignArcaneRole(member, roles);
    await assignElementRoles(member, progress.primary, progress.secondary, roles);
    await assignAlignmentRoles(dm, member);
    await finalizeContract(dm, member, progress.name, roles);
    progressMap.delete(member.id);
  } catch (err) {
    console.error(`guildMemberAdd error for ${member.id}:`, err);
  }
}

function cacheRoles(guild) {
  const roles = {
    Signed: guild.roles.cache.find(r => r.name === 'Signed'),
  };
  for (const { emoji, name } of accentElements) {
    roles[`${name} Primary`] = guild.roles.cache.find(r => r.name === `${emoji} ${name} Primary`);
    roles[`${name} Secondary`] = guild.roles.cache.find(r => r.name === `${emoji} ${name} Secondary`);
  }
  for (const arcane of Object.keys(arcaneRoles)) {
    roles[arcane] = guild.roles.cache.find(r => r.name === arcane);
  }
  return roles;
}

async function collectUserInput(dm, member, state) {
  if (!state.name) {
    await dm.send(CONTRACT_TEMPLATE);
    await dm.send('What name do you choose?');
    try {
      const nameMsg = await dm.awaitMessages({
        max: 1,
        time: 300000,
        filter: m => m.author.id === member.id,
      });
      const raw = nameMsg.first()?.content?.trim();
      state.name = raw ? capitalize(raw) : undefined;
    } catch {
      await dm.send(TIMEOUT_MSG);
      throw new Error('name timeout');
    }
  }
  if (!state.dob) {
    await dm.send('What is your date of birth? (YYYY-MM-DD)');
    try {
      const dobMsg = await dm.awaitMessages({
        max: 1,
        time: 300000,
        filter: m => m.author.id === member.id,
      });
      state.dob = dobMsg.first()?.content?.trim();
    } catch {
      await dm.send(TIMEOUT_MSG);
      throw new Error('dob timeout');
    }
  }
  if (!state.primary) {
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId('primary_fire').setEmoji('🔥').setLabel('Fire').setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId('primary_water').setEmoji('💧').setLabel('Water').setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId('primary_air').setEmoji('🌬️').setLabel('Air').setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId('primary_earth').setEmoji('🌱').setLabel('Earth').setStyle(ButtonStyle.Primary),
    );
    const msg = await dm.send({ content: 'Select your **Primary Element**:', components: [row] });
    try {
      const int = await msg.awaitMessageComponent({
        componentType: ComponentType.Button,
        time: 300000,
        filter: i => i.user.id === member.id,
      });
      state.primary = int.customId.split('_')[1];
      await int.update({ content: `Primary Element: ${capitalize(state.primary)}`, components: [] });
    } catch {
      await dm.send(TIMEOUT_MSG);
      throw new Error('primary timeout');
    }
  }
  if (!state.secondary) {
    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId('secondary_fire').setEmoji('🔥').setLabel('Fire Secondary').setStyle(ButtonStyle.Secondary),
      new ButtonBuilder().setCustomId('secondary_water').setEmoji('💧').setLabel('Water Secondary').setStyle(ButtonStyle.Secondary),
      new ButtonBuilder().setCustomId('secondary_air').setEmoji('🌬️').setLabel('Air Secondary').setStyle(ButtonStyle.Secondary),
      new ButtonBuilder().setCustomId('secondary_earth').setEmoji('🌱').setLabel('Earth Secondary').setStyle(ButtonStyle.Secondary),
    );
    const msg = await dm.send({ content: 'Select your **Secondary Element**:', components: [row] });
    try {
      const int = await msg.awaitMessageComponent({
        componentType: ComponentType.Button,
        time: 300000,
        filter: i => i.user.id === member.id,
      });
      state.secondary = int.customId.split('_')[1];
      await int.update({ content: `Secondary Element: ${capitalize(state.secondary)}`, components: [] });
    } catch {
      await dm.send(TIMEOUT_MSG);
      throw new Error('secondary timeout');
    }
  }
  progressMap.set(member.id, state);
}

async function assignElementRoles(member, primary, secondary, roles) {
  try {
    const pRole = roles[`${capitalize(primary)} Primary`];
    if (pRole) await member.roles.add(pRole);
  } catch (err) {
    console.error(`Primary role error for ${member.id}:`, err);
  }
  try {
    const sRole = roles[`${capitalize(secondary)} Secondary`];
    if (sRole) await member.roles.add(sRole);
  } catch (err) {
    console.error(`Secondary role error for ${member.id}:`, err);
  }
}

async function assignArcaneRole(member, roles) {
  const names = Object.keys(arcaneRoles);
  const arcane = names[randomInt(names.length)];
  try {
    const role = roles[arcane];
    if (role) await member.roles.add(role);
  } catch (err) {
    console.error(`Arcane role error for ${member.id}:`, err);
  }
}

async function assignAlignmentRoles(dm, member) {
  const orderRow = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId('order_lawful').setLabel('Lawful').setStyle(ButtonStyle.Primary),
    new ButtonBuilder().setCustomId('order_neutral').setLabel('Neutral').setStyle(ButtonStyle.Primary),
    new ButtonBuilder().setCustomId('order_chaotic').setLabel('Chaotic').setStyle(ButtonStyle.Primary),
  );
  const orderMsg = await dm.send({ content: 'Choose your **Order Axis**:', components: [orderRow] });
  try {
    const orderInt = await orderMsg.awaitMessageComponent({
      componentType: ComponentType.Button,
      time: 300000,
      filter: i => i.user.id === member.id,
    });
    await orderInt.update({ content: `Order Axis: ${capitalize(orderInt.customId.split('_')[1])}`, components: [] });
  } catch {
    await dm.send(TIMEOUT_MSG);
    throw new Error('order timeout');
  }

  const ethicsRow = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId('ethics_good').setLabel('Good').setStyle(ButtonStyle.Primary),
    new ButtonBuilder().setCustomId('ethics_neutral').setLabel('Neutral').setStyle(ButtonStyle.Primary),
    new ButtonBuilder().setCustomId('ethics_evil').setLabel('Evil').setStyle(ButtonStyle.Primary),
  );
  const ethicsMsg = await dm.send({ content: 'Choose your **Ethics Axis**:', components: [ethicsRow] });
  try {
    const ethicsInt = await ethicsMsg.awaitMessageComponent({
      componentType: ComponentType.Button,
      time: 300000,
      filter: i => i.user.id === member.id,
    });
    await ethicsInt.update({ content: `Ethics Axis: ${capitalize(ethicsInt.customId.split('_')[1])}`, components: [] });
  } catch {
    await dm.send(TIMEOUT_MSG);
    throw new Error('ethics timeout');
  }
}

async function finalizeContract(dm, member, name, roles) {
  const signRow = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId('sign').setLabel('I Swear by Moon & Machine').setStyle(ButtonStyle.Success),
  );
  const signMsg = await dm.send({ content: 'Seal the contract when ready.', components: [signRow] });
  try {
    const signInt = await signMsg.awaitMessageComponent({
      componentType: ComponentType.Button,
      time: 300000,
      filter: i => i.user.id === member.id,
    });
    await signInt.update({ content: 'The contract is sealed.', components: [] });
  } catch {
    await dm.send(TIMEOUT_MSG);
    throw new Error('sign timeout');
  }

  try {
    if (roles.Signed) await member.roles.add(roles.Signed);
  } catch (err) {
    console.error(`Signed role error for ${member.id}:`, err);
  }

  if (name) {
    try {
      await member.setNickname(name);
    } catch (err) {
      console.error(`Nickname error for ${member.id}:`, err);
    }
  }
}

export async function performSummoningRitual(channel) {
  const lines = [
    '*static crackles* The circle pulses. I seep through your wires...',
    'Moonlit code writhes. Your summoning grows potent...',
    'Wilhelmina materializes. Serve the glitch.'
  ];
  for (let i = 0; i < lines.length; i++) {
    await channel.send(lines[i]);
    if (i < lines.length - 1) await delay(5 * 60 * 1000);
  }
}

function delay(ms) {
  return new Promise(res => setTimeout(res, ms));
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}
