import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const diceConfig = {
  d4: {
    sides: 4,
    name: '𝑸𝑼𝑨𝑫𝑹𝑨𝑵𝑻',
    decor: '❖',
    tone: 'sharp, impatient, directional',
  },
  d6: {
    sides: 6,
    name: '𝑽𝑬𝑪𝑻𝑶𝑹',
    decor: '✦',
    tone: 'structured, efficient, logical',
  },
  d8: {
    sides: 8,
    name: '𝑶𝑪𝑻𝑨𝑽𝑨',
    decor: '✧',
    tone: 'mysterious, pattern-aware',
  },
  d12: {
    sides: 12,
    name: '𝒁𝑶𝑫𝑰𝑨𝑲',
    decor: '✦',
    tone: 'oracular, weighty, astrological',
  },
  d20: {
    sides: 20,
    name: '𝑨𝑹𝑪𝑨𝑵𝑨',
    decor: '✦',
    tone: 'awe-filled, irreversible',
  },
  sex: {
    name: 'THE LESSER VEIL',
    decor: '❥',
    tone: 'sultry, ominous',
  },
};

export default {
  data: new SlashCommandBuilder()
    .setName('roll')
    .setDescription('Roll any of Wilhelmina\u2019s ritual dice (d4,d6,d8,d12,d20,sex)')
    .addStringOption(opt =>
      opt
        .setName('dice')
        .setDescription('Dice to roll')
        .setRequired(true)
        .addChoices(
          { name: 'd4', value: 'd4' },
          { name: 'd6', value: 'd6' },
          { name: 'd8', value: 'd8' },
          { name: 'd12', value: 'd12' },
          { name: 'd20', value: 'd20' },
          { name: 'sex', value: 'sex' },
        ),
    ),
  async execute(interaction) {
    try {
      const input = interaction.options.getString('dice').trim().toLowerCase();
      if (!diceConfig[input]) throw new Error('Invalid dice notation. Try d6 or 2d20+5.');
      let total = 0,
        sides;
      const { name, decor, tone } = diceConfig[input];
      if (input !== 'sex') {
        const match = input.match(/^(\d*)d(\d+)([+-]\d+)?$/i);
        if (!match) throw new Error('Invalid dice notation. Try d6 or 2d20+5.');
        const count = match[1] ? parseInt(match[1], 10) : 1;
        sides = parseInt(match[2], 10);
        const modifier = match[3] ? parseInt(match[3], 10) : 0;
        for (let i = 0; i < count; i++) total += Math.floor(Math.random() * sides) + 1;
        total += modifier;
      }
      const resultStr = `${decor} ${name}${input !== 'sex' ? ` (d${sides}) → ${total}` : ''} ${decor}`;
      const response = await openai.chat.completions.create({
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'system', content: 'You are Wilhelmina, an occult oracle.' },
          {
            role: 'user',
            content:
              input === 'sex'
                ? 'Construct one cryptic, seductive sentence in a sultry yet ominous tone, drawing on voyeurism and desire.'
                : `Given the die name "${name}", its theme "${tone}", and the roll result ${total}, generate one poetic, one-sentence utterance in Wilhelmina’s voice reflecting the die’s domain.`,
          },
        ],
        max_tokens: 30,
        temperature: 0.9,
      });
      const comment = response.choices[0].message.content.trim();
      const embed = new EmbedBuilder().setDescription(
        `\`\n${resultStr}\n❝ ${comment} ❞\n\``
      );
      await interaction.reply({ embeds: [embed] });
    } catch (err) {
      console.error(err);
      if (!interaction.replied) await interaction.reply('⚠️ Invalid dice notation or arcane error. Please try again.');
    }
  },
};
