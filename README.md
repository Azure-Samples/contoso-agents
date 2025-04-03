# Contoso Agents

This is sample application for the Contoso Agents project, which demonstrates how to build autonomous agents that can process incoming orders via email. The agents are designed to work with Microsoft Copilot Studio and Microsoft Teams, allowing users to review and approve orders through a user-friendly interface.

## Features

- Autonomous agents process incoming orders via email
- User can the review and approve orders interacting with the agents over Copilot Studio or Teams

## Getting Started

### Prerequisites

- Python 3.12 or later
- Azure Deverloper CLI

### Quickstart

> [!IMPORTANT]
> In order to start the deployment, you must first create an Entra ID App Registration with a client secret.
> This is required for the Azure Bot Service to work.

> [!TIP]
> You can create the Entra ID App Registration using the Azure CLI with the following command:

```bash
az ad app create --display-name "Contoso Agents Bot"
az ad app credential reset --id [app-id from previous command]
```

Now you can start the deployment:

1. `git clone [repository clone url]`
2. `cd [repository name]`
3. `azd up`

> [!IMPORTANT]
> When prompted, input `botAppId`, `botAppPassword`, and `botAppTenantId` with the values from the Entra ID App Registration you created earlier.
>
> Additionally, you must also provide `openAIName` and `openAIResourceGroupName` of an existing OpenAI resource in your Azure subscription.

> [!NOTE]
> The deployment will take a few minutes to complete. The script will also run some post-provisioning tasks:
>
> - Update App Registration with the correct homepage URL (as required by Copilot Studio)
> - Seed the database with some sample data

## Running locally

Part of this application can be run locally for development purposes. To do this, you need to set up a local environment and install the required dependencies.

1. Create a virtual environment and activate it:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use .venv\Scripts\activate
```

2. Install the required dependencies:

```bash
pip install -r src/agents/requirements.txt
pip install -r src/admin/requirements.txt
pip install -r src/skill/requirements.txt
```

3. Set up `.env` file with the required environment variables. You can use the `.env.example` file as a reference.

> [!TIP]
> After you deploy the application, you can find the required environment variables under `.azure/<env name>/.env`.
>
> You can copy those values to your local `.env` file.

## Resources

(Any additional resources or related projects)

- Link to supporting information
- Link to similar sample
- ...

## Contributing

Please read the [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
