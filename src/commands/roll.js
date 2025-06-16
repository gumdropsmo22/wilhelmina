import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import OpenAI from 'openai';

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

export default {
  data: new SlashCommandBuilder()
    .setName('roll')
    .setDescription('Roll any of Wilhelmina’s ritual dice (d4,d6,d8,d12,d20,sex)')
    .addStringOption(opt =>
      opt.setName('dice')
        .setDescription('Dice to roll')
        .setRequired(true)
        .addChoices(
          { name: 'd4', value: 'd4' },
          { name: 'd6', value: 'd6' },
          { name: 'd8', value: 'd8' },
          { name: 'd12', value: 'd12' },
          { name: 'd20', value: 'd20' },
          { name: 'sex', value: 'sex' },
        )
    ),
  async execute(interaction) {
    try {
      const input = interaction.options.getString('dice');
      const diceConfig = {
        d4: { sides: 4, name: '𝑸𝑼𝑨𝑫𝑹𝑨𝑵𝑻', decor: '⁂' },
        d6: { sides: 6, name: '𝑽𝑬𝑪𝑻𝑶𝑹', decor: '✷' },
        d8: { sides: 8, name: '𝑶𝑪𝑻𝑨𝑽𝑨', decor: '✸' },
        d12: { sides: 12, name: '𝒁𝑶𝑫𝑰𝑨𝑲', decor: '✹' },
        d20: { sides: 20, name: '𝑨𝑹𝑪𝑨𝑵𝑨', decor: '✺' },
        sex: { name: 'THE LESSER VEIL', decor: '♡' },
      };

      let total = 0;
      let sides;
      const { name, decor } = diceConfig[input] || {};
      const tone = name;

      if (input !== 'sex') {
        const match = input.match(/^(\d*)d(\d+)([+-]\d+)?$/i);
        if (!match) throw new Error('Invalid dice notation. Try d6 or 2d20+5.');
        const count = match[1] ? parseInt(match[1], 10) : 1;
        sides = parseInt(match[2], 10);
        const modifier = match[3] ? parseInt(match[3], 10) : 0;
        for (let i = 0; i < count; i++) {
          total += Math.floor(Math.random() * sides) + 1;
        }
        total += modifier;
      }

      const resultStr = `${decor} ${name}${input !== 'sex' ? ` (d${sides}) → ${total}` : ''} ${decor}`;

      const response = await openai.chat.completions.create({
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'system', content: 'You are Wilhelmina, an occult oracle.' },
          {
            role: 'user',
            content: input === 'sex'
              ? 'Construct one cryptic, seductive sentence...'
              : `Given the die name "${name}", theme "${tone}", and result ${total}, generate one poetic utterance in Wilhelmina’s voice.`,
          },
        ],
        max_tokens: 30,
        temperature: 0.9,
      });
      const comment = response.choices[0].message.content.trim();

      const embed = new EmbedBuilder().setDescription(`\`\`\`
${resultStr}
❝ ${comment} ❞
\`\`\``);
      await interaction.reply({ embeds: [embed] });
    } catch (err) {
      console.error(err);
      if (!interaction.replied) {
        await interaction.reply('⚠️ Invalid or arcane error.');
      }
    }
  },
};
