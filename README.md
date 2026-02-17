# JetAssist for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/release/jethome-ru/ha-jethome-cloud.svg)](https://github.com/jethome-homeassistant/ha-jethome-cloud/releases)

Custom integration for [Home Assistant](https://www.home-assistant.io/) that connects
your HA instance to [JetAssist](https://jethome.cloud) platform.

## Features

- **Remote Access** -- secure tunnel to access Home Assistant from anywhere
  (like Nabu Casa Remote UI)
- **Cloud Backups** -- automatic backups to S3-compatible storage with E2E encryption
- **AI Assistant** (coming soon) -- voice control via STT/TTS and LLM with
  smart home context

## Installation

### HACS (recommended)

1. Open **HACS** in Home Assistant sidebar
2. Click **Integrations** -> three dots menu -> **Custom repositories**
3. Add repository URL: `https://github.com/jethome-homeassistant/ha-jethome-cloud`
4. Category: **Integration**
5. Click **Add**, then find **JetAssist** and click **Download**
6. Restart Home Assistant

### Manual

1. Copy `custom_components/jethome_cloud/` to your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** -> **Devices & Services** -> **+ Add Integration**
2. Search for **JetAssist**
3. Choose authentication method:
   - **OAuth2 Login** (recommended) -- opens browser for Authentik login
   - **API Token** -- manual token from `https://auth.jethome.cloud/`
4. Enable/disable remote access tunnel

## Registration

Create an account at `https://auth.jethome.cloud/`:
- **Email + password** with email verification
- **Social login**: GitHub, Google, Yandex ID

## Remote Access

After setup, your HA is accessible at `https://<your-id>.tun.jethome.cloud`.
The tunnel:
- Works through WebSocket -- passes corporate proxies and firewalls
- Encrypted with TLS (WSS)
- Auto-reconnects on connection loss
- No port forwarding or static IP required

## Cloud Backups

The integration registers as a Backup Agent in Home Assistant:
- **Settings** -> **System** -> **Backups** -> select **JetAssist** as location
- E2E encrypted -- cloud cannot read your data
- Schedule via HA automations

## Documentation

- [Server Deployment](https://docs.jethome.cloud/deployment)
- [Integration Guide](https://docs.jethome.cloud/ha-integration-guide)
- [Architecture](https://docs.jethome.cloud/architecture)

## License

Proprietary. See [LICENSE](LICENSE).

## Support

- Issues: https://github.com/jethome-homeassistant/ha-jethome-cloud/issues
- Telegram: https://t.me/jethome
