# Wilhelmina Bot

Wilhelmina is a Discord bot that offers onboarding assistance, tarot readings, voice interactions and administrative tools. It is designed to help manage your server while providing fun and useful commands for members.

## Prerequisites

- **Node.js** v16 or newer
- **Git** for cloning the repository
- **MongoDB** instance for data storage
- A configured **Discord application** with bot token, client ID, and guild ID

## Installation

1. Clone the repository
   ```bash
   git clone https://github.com/your-org/wilhelmina.git
   cd wilhelmina
   ```
2. Run the bootstrap script to install dependencies and create a base `.env` file
   ```bash
   ./bootstrap.sh
   ```

## Configuration

Copy `.env.example` to `.env` and edit the values for your environment:
```bash
cp .env.example .env
# then edit .env with your favorite editor
```
Required now:
- `DISCORD_TOKEN`
Optional placeholders for later tasks:
- `OPENAI_API_KEY`, `MONGO_URL`, `TZ=Asia/Riyadh`
Never commit real secrets.

## Usage

The project exposes several npm scripts. Use `npm run <script>` to execute them.

| Script       | Purpose                                        |
|--------------|------------------------------------------------|
| `start`      | Launch the production bot                      |
| `dev`        | Start the bot in development mode with reloads |
| `test`       | Run project tests                              |
| `lint`       | Lint the codebase for style issues             |
| `deploy-commands` | Register/update slash commands            |

## Contributing

Contributions are welcome! Fork the repository, create a feature branch, and open a pull request describing your changes. Please keep commits concise and follow existing coding conventions.

Enable local hooks (first time only):

```bash
pre-commit install
```

## License

MIT © 2025
