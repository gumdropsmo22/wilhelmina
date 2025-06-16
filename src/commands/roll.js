import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import OpenAI from 'openai';

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const diceConfig = {
  d4: { sides: 4, name: '𝑸𝑼𝑨𝑫𝑹𝑨𝑵𝑻', decor: '❖', tone: 'sharp, impatient, directional' },
  d6: { sides: 6, name: '𝑽𝑬𝑪𝑻𝑶𝑹', decor: '✦', tone: 'structured, efficient, logical' },
  d8: { sides: 8, name: '𝑶𝑪𝑻𝑨𝑽𝑨', decor: '✧', tone: 'mysterious, pattern-aware' },
  d12: { sides: 12, name: '𝒁𝑶𝑫𝑰𝑨𝑲', decor: '✦', tone: 'oracular, weighty, astrological' },
  d20: { sides: 20, name: '𝑨𝑹𝑪𝑨𝑵𝑨', decor: '✦', tone: 'awe-filled, irreversible' },
  sex: { name: 'THE LESSER VEIL', decor: '❥', tone: 'sultry, ominous' }
};

const positions = [
  'Missionary Hex','Ride the Circle','Reverse Ritual','The Hound’s Blessing',
  'Twinned Fates','The Cuddle Curse','The Upright Pact','The Wall Ritual',
  'The Split Summons','The Arc of Submission','The Throne Seat','The Hanging Rite'
];

const acts = [
  'Hex the Lips','Lick the Sigil','Draw the Hex','Ride the Glyph','Stir the Cauldron',
  'Cast the Feel','Smite the Cheek','Pet the Familiar','Mute the Oracle','Grip the Wand',
  'Summon the Sting','Warm the Relic','Snare the Breath','Point the Path','Gnaw the Offering'
];

const locations = [
  'On the Altar','Behind the Red Curtain','In the Circle of Salt','Against the Library Wall',
  'Within the Confession Booth','Beneath the Stair','In the Ninth Chamber','Under Candlelight',
  'On the Summoning Sigil','In the Tithing Hall'
];

export default {
  data: new SlashCommandBuilder()
    .setName('roll')
    .setDescription('Roll any of Wilhelmina’s ritual dice (d4,d6,d8,d12,d20,sex)')
    .addStringOption(opt =>
      opt
        .setName('dice')
        .setDescription('Dice to roll')
        .setRequired(true)
        .addChoices(
          { name: 'd4',  value: 'd4' },
          { name: 'd6',  value: 'd6' },
          { name: 'd8',  value: 'd8' },
          { name: 'd12', value: 'd12' },
          { name: 'd20', value: 'd20' },
          { name: 'sex', value: 'sex' },
        )
    ),

  async execute(interaction) {
    try {
      const input = interaction.options.getString('dice').trim().toLowerCase();
      if (!diceConfig[input]) {
        throw new Error('Invalid dice notation. Try d6 or 2d20+5.');
      }

      const { name, decor, tone } = diceConfig[input];
      let total = 0;
      let sides;

      // Sex die flow
      if (input === 'sex') {
        const position = positions[Math.floor(Math.random() * positions.length)];
        const act      = acts[Math.floor(Math.random() * acts.length)];
        const location = locations[Math.floor(Math.random() * locations.length)];

        const response = await openai.chat.completions.create({
          model: 'gpt-3.5-turbo',
          messages: [
            { role: 'system', content: 'You are Wilhelmina, an occult oracle.' },
            {
              role: 'user',
              content: `Generate a short, gender-neutral one-liner spoken by an ancient, sarcastic witch after observing a sexual ritual with position "${position}", act "${act}", location "${location}". The tone must fall into one of the following: Dry Roast, Mocking Awe, Cosmic Disgust, Ritual Inspection. References to anatomy or acts are allowed only if subtle, clever, or metaphorical. No explicit language. No gendered terms. No porn tropes. 18 words max.`
            }
          ],
          max_tokens: 50,
          temperature: 0.9
        });

        const comment   = response.choices[0].message.content.trim();
        const resultStr = `${decor} ${name} ${decor}`;
        const embed     = new EmbedBuilder().setDescription(
          `\`\`\`\n${resultStr}\n❝ ${comment} ❞\n\`\`\``
        );

        await interaction.reply({ embeds: [embed] });
        return;
      }

      // Numeric dice flow
      const match = input.match(/^(\d*)\s*d\s*(\d+)([+\-]\s*\d+)?$/i);
      if (!match) {
        throw new Error('Invalid dice notation. Try d6 or 2d20+5.');
      }

      const count    = match[1] ? parseInt(match[1], 10) : 1;
      sides          = parseInt(match[2], 10);
      const modifier = match[3] ? parseInt(match[3].replace(/\s+/g, ''), 10) : 0;

      for (let i = 0; i < count; i++) {
        total += Math.floor(Math.random() * sides) + 1;
      }
      total += modifier;

      const resultStr = `${decor} ${name} (d${sides}) → ${total} ${decor}`;

      const response = await openai.chat.completions.create({
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'system', content: 'You are Wilhelmina, an occult oracle.' },
          {
            role: 'user',
            content: `Given the die name "${name}", its theme "${tone}", and the roll result ${total}, generate one poetic, one-sentence utterance in Wilhelmina’s voice reflecting the die’s domain.`
          }
        ],
        max_tokens: 30,
        temperature: 0.9
      });

      const comment = response.choices[0].message.content.trim();
      const embed   = new EmbedBuilder().setDescription(
        `\`\`\`\n${resultStr}\n❝ ${comment} ❞\n\`\`\``
      );

      await interaction.reply({ embeds: [embed] });
    } catch (err) {
      console.error(err);
      if (!interaction.replied) {
        await interaction.reply('⚠️ Invalid dice notation or arcane error. Please try again.');
      }
    }
  }
};
