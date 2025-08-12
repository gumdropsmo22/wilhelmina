import { SlashCommandBuilder } from 'discord.js';
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export default {
  data: new SlashCommandBuilder()
    .setName('openbisquitte')
    .setDescription('Crack open a mystical biscuit'),
  async execute(interaction) {
    try {
      const prompt = 'Provide a short, mystical fortune as if from a fortune cookie.';
      const chat = await openai.chat.completions.create({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 30,
        temperature: 0.8,
      });

      let fortune = chat?.choices?.[0]?.message?.content?.trim();
      if (!fortune) fortune = 'The biscuit has crumbled into silence.';

      const templates = [
        `╔═══════ ❖ 𝕺𝖕𝖊𝖓𝕭𝖎𝖘𝖖𝖚𝖎𝖙𝖙𝖊 ❖ ═══════╗
       🜁  A parchment unfurls within the crumbs...
       ❝ {fortune} ❞
╚═════════════════════════════════╝`,
        `╭┈────── ∘°❉°∘ ──────┈╮
     🥠 𝓞𝓹𝓮𝓷𝓑𝓲𝓼𝓺𝓾𝓲𝓽𝓽𝓮 𝓌𝒽𝒾𝓈𝓅𝑒𝓇𝓈...
     ❝ {fortune} ❞
╰┈────── ∘°❉°∘ ──────┈╯`,
        `╔═━「 ✦ 𝒪𝓅𝑒𝓃 𝐵𝒾𝓈𝓆𝓊𝒾𝓉𝓉𝑒 ✦ 」━═╗
    ✦ [The bisquitte has spoken.] ✦
    ❝ {fortune} ❞
╚══════════════════════════════════╝`,
        `╓───── ·𖥸· ─────╖
  🍪 𝒪𝓅𝑒𝓃 𝐵𝒾𝓈𝒸𝓊𝒾𝓉𝓉𝑒
  ❝ {fortune} ❞
╙───── ·𖥸· ─────╜`,
        `╭🌙⋆⁺₊❖ 𝒪𝓅𝑒𝓃𝐵𝒾𝓈𝓆𝓊𝒾𝓉𝓉𝑒 ❖₊⁺⋆🌙╮
     🜃 “{fortune}”
╰🌙⋆⁺₊───────────────₊⁺⋆🌙╯`,
      ];

      const template = templates[Math.floor(Math.random() * templates.length)];
      const content = template.replace('{fortune}', fortune);

      await interaction.reply({ content });
    } catch (error) {
      console.error(error);
      if (!interaction.replied) {
        await interaction.reply('⚠️ Something went wrong. Please try again later.');
      }
    }
  },
};