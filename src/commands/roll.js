import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import OpenAI from 'openai';

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const diceConfig = {
  4: { name: '𝑸𝑼𝑨𝑫𝑹𝑨𝑵𝑻', decor: '❖', tone: 'sharp, impatient, directional' },
  6: { name: '𝑯𝑬𝑿', decor: '✶', tone: 'measured, deliberate, cunning' },
  8: { name: '𝑶𝑪𝑻𝑨𝑽𝑬', decor: '✥', tone: 'cyclical, watchful, enduring' },
  12: { name: '𝑫𝑼𝑫𝑬𝑪𝑰𝑴', decor: '✺', tone: 'majestic, fateful, perennial' },
  20: { name: '𝑰𝑪𝑶𝑺', decor: '✷', tone: 'cosmic, revolutionary, transcendent' },
  sex: { name: 'THE LESSER VEIL', decor: '✴', tone: 'sultry, ominous' },
};

export default {
  data: new SlashCommandBuilder()
    .setName('roll')
    .setDescription('Roll any of Wilhelmina\u2019s ritual dice (d4,d6,d8,d12,d20,sex)')
    .addStringOption(opt =>
      opt
        .setName('dice')
        .setDescription('Dice to roll, e.g. 2d6+1, d20, sex')
        .setRequired(true)
    ),

  async execute(interaction) {
    try {
      const input = interaction.options.getString('dice').toLowerCase();
      let resultStr = '';
      let name = '';
      let decor = '';
      let tone = '';
      let total = 0;

      if (input === 'sex') {
        ({ name, decor, tone } = diceConfig.sex);
        resultStr = `${decor} ${name} ${decor}`;
      } else {
        const match = input.match(/^(\d*)d(\d+)([+-]\d+)?$/);
        if (!match) {
          throw new Error('Invalid dice notation');
        }

        const count = match[1] ? parseInt(match[1], 10) : 1;
        const sides = parseInt(match[2], 10);
        const modifier = match[3] ? parseInt(match[3], 10) : 0;

        ({ name, decor, tone } = diceConfig[sides] || { name: `d${sides}`, decor: '•', tone: 'mysterious' });

        const rolls = [];
        for (let i = 0; i < count; i += 1) {
          rolls.push(Math.floor(Math.random() * sides) + 1);
        }
        total = rolls.reduce((sum, r) => sum + r, 0) + modifier;

        resultStr = `${decor} ${name} (d${sides}) → ${total} ${decor}`;
      }

      const aiPrompt =
        input === 'sex'
          ? 'Construct one cryptic, seductive sentence in a sultry yet ominous tone, drawing on voyeurism and desire.'
          : `Given the die name "${name}", its theme "${tone}", and the roll result ${total}, generate one poetic, one-sentence utterance in Wilhelmina\u2019s voice reflecting the die\u2019s domain.`;

      const completion = await openai.completions.create({
        model: 'text-davinci-003',
        prompt: aiPrompt,
        max_tokens: 30,
        temperature: 0.9,
      });

      const comment = completion.choices[0].text.trim();
      const embed = new EmbedBuilder().setDescription(
        `\`\`\`\n${resultStr}\n❝ ${comment} ❞\n\`\`\``
      );

      await interaction.reply({ embeds: [embed] });
    } catch (err) {
      console.error(err);
      if (!interaction.replied) {
        await interaction.reply('⚠️ The arcane forces balked. Please try again.');
      }
    }
  },
};
