import { SlashCommandBuilder } from 'discord.js';
import dotenv from 'dotenv';
import OpenAI from 'openai';

dotenv.config();

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const templates = [
  '🥠 **Fortune**: {fortune}',
  '🧿 The biscuit whispers, "{fortune}"',
  '✨ A crumb of wisdom: {fortune}',
  '🔮 Prophecy: {fortune}'
];

export default {
  data: new SlashCommandBuilder()
    .setName('openbisquitte')
    .setDescription('Crack open a mystical biscuit'),
  async execute(interaction) {
    const prompt = 'Provide a short, mystical fortune as if from a fortune cookie.';
    const chat = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 30,
      temperature: 0.8,
    });

    let fortune = chat?.choices?.[0]?.message?.content?.trim();
    if (!fortune) fortune = 'The biscuit has crumbled into silence.';

    const template = templates[Math.floor(Math.random() * templates.length)];
    const content = template.replace('{fortune}', fortune);

    await interaction.reply({ content });
  }
};

