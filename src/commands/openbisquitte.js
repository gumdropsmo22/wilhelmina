import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export default {
  data: new SlashCommandBuilder()
    .setName('openbisquitte')
    .setDescription('Summon a stylized fortune from Wilhelmina\u2019s cracked pastry of fate.'),
  async execute(interaction) {
    try {
      const completion = await openai.completions.create({
        model: 'text-davinci-003',
        prompt:
          'Generate a one-sentence fortune that could be delivered by a surreal, magical biscuit in a whimsical yet ominous world. The tone should be randomly chosen between hopeful, cryptic, or dark, and the language should be poetic, metaphorical, or unsettling. Avoid clich\u00e9s and fortune cookie tropes\u2014favor strange imagery, subtle tension, or quiet beauty.',
        max_tokens: 30,
        temperature: 0.8,
      });

      const fortune = completion.choices[0].text.trim();

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
      const message = template.replace('{fortune}', fortune);

      await interaction.reply({ content: message });
    } catch (error) {
      console.error(error);
      if (!interaction.replied) {
        await interaction.reply('⚠️ Something went wrong. Please try again later.');
      }
    }
  },
};
