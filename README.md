# Amazon Bedrock AgentCore Crash Course

This crash course is a hands-on path for building a bank FAQ assistant with RAG, AgentCore runtime deployment, and AgentCore Memory.

The examples in this lab use `bank_faq.csv` as the knowledge base. The CSV contains banking FAQ questions and answers, and each agent searches this file before generating a response.

## Course Structure

This course focuses on three files:

1. `001_lg_agent_fast_embeddings.py`
   - Local LangGraph/LangChain FAQ agent.
   - Uses `bank_faq.csv` for RAG.
   - Uses `FastEmbedEmbeddings` instead of sentence-transformers to keep dependencies lightweight.

2. `002_agentcore_runtime_fast_embeddings.py`
   - AgentCore runtime version of the FAQ RAG agent.
   - Uses `bank_faq.csv` and FAISS search.
   - Returns a clean `answer` field for the frontend UI.
   - Uses fast embeddings so the AWS build stays smaller.

3. `003_agentcore_memory_fast.py`
   - AgentCore runtime agent with RAG plus AgentCore Memory.
   - Uses `bank_faq.csv`, FAISS, fast embeddings, and `MEMORY_ID`.
   - Supports UI calls with `actor_id` and `thread_id` so follow-up questions can use session memory.

## Setup and Prerequisites

### System Requirements

- Python 3.13 or newer
- Windows, macOS, Linux, or an EC2 Ubuntu environment
- `uv` for dependency installation
- AWS CLI configured with credentials
- AgentCore CLI installed and working

Check Python:

```bash
python --version
```

Install `uv`:

```bash
pip install uv
```

Install project dependencies:

```bash
uv sync
```

### AWS Requirements

AdministratorAccess 
AmazonBedrockFullAccess 
AWSCodeBuildAdminAccess
BedrockAgentCoreFullAccess

Use an AWS account with access to Amazon Bedrock AgentCore. For this lab, the user/role should have permissions for Bedrock AgentCore, CodeBuild, IAM role creation, CloudWatch Logs, ECR, and related resources created by `agentcore launch`.

Check your identity:

```bash
aws sts get-caller-identity
```

Check AgentCore CLI:

```bash
agentcore --help
```

Set your AWS region:

```bash
export AWS_DEFAULT_REGION=us-east-1
```

On PowerShell:

```powershell
$env:AWS_DEFAULT_REGION="us-east-1"
```

### Environment Variables

Create a `.env` file in the project root:

```bash
touch .env
```

Add your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
```

For the memory lab, you can also provide your AgentCore memory id:

```env
MEMORY_ID=your_agentcore_memory_id_here
```

## Dataset

The lab uses:

```text
bank_faq.csv
```

The file must contain these columns:

```csv
question,answer
```

The agents load the CSV, split the FAQ entries into chunks, embed the chunks with FastEmbed, store them in FAISS, and retrieve relevant FAQ entries at question time.

## Running the Labs

### 001: Local RAG Agent

Run the local agent:

```bash
python 001_lg_agent_fast_embeddings.py
```

This validates the RAG flow locally before deploying to AgentCore.

### 002: AgentCore Runtime RAG Agent

Configure the runtime:
```bash
uv sync
activate the environment
```

```bash
export AWS_DEFAULT_REGION=us-east-1
agentcore configure -e agentcore_runtime_fast_embedding.py
```

Launch the agent:

```bash
agentcore launch --env GROQ_API_KEY=$GROQ_API_KEY
```

Test it:

```bash
agentcore invoke '{"prompt": "Can I use my card in Europe without extra charges?"}'
```

This agent returns:

```json
{"answer": "..."}
```

That response shape is compatible with the frontend UI in `with_ui`.

### 003: AgentCore Runtime RAG Agent with Memory

Set your memory id:

```bash
export MEMORY_ID="your_agentcore_memory_id_here"
export GROQ_API_KEY="your_groq_api_key_here"
```

Configure the memory agent:

```bash
agentcore configure -e 003_agentcore_memory_fast.py
```

Launch the agent:

```bash
agentcore launch --env GROQ_API_KEY=$GROQ_API_KEY --env MEMORY_ID=$MEMORY_ID
```

Test memory behavior:

```bash
agentcore invoke '{"prompt": "Can I use my card in Europe without extra charges?", "actor_id": "web-user", "thread_id": "web-chat"}'
agentcore invoke '{"prompt": "which country i was talking about in my last question ?", "actor_id": "web-user", "thread_id": "web-chat"}'
agentcore invoke '{"prompt": "Remember my preference and answer my question", "actor_id": "web-user", "thread_id": "web-chat"}'
```

Use the same `actor_id` and `thread_id` when testing follow-up questions, otherwise the memory context may not match the previous conversation.

## Frontend UI

The frontend lives in:

```text
with_ui
```

The UI sends:

- `prompt`
- `actor_id`
- `thread_id`
- `agent_id`

The deployed AgentCore runtime should return:

```json
{"answer": "..."}
```

For the memory lab, point the UI Agent Key to the deployed agent configured from `003_agentcore_memory_fast.py`.

## Additional Resources

- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-get-started-toolkit.html/)
- [Amazon Bedrock AgentCore Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
- [Adding memory to an existing agent](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-get-started.html#memory-add-to-existing-agent)
## Cleanup: Delete Agents and Lab Resources

Run cleanup after the lab to avoid keeping unused AWS resources.

### Delete an AgentCore agent

List configured/local agents:

```bash
agentcore configure list
```

Destroy a deployed agent by key/name:

```bash
agentcore destroy --agent AGENTNAME
```

Example:

```bash
agentcore destroy --agent banking_agent
```

If your CLI prompts for confirmation, confirm the deletion.

### Delete CloudWatch log groups

Find AgentCore runtime log groups:

```bash
aws logs describe-log-groups \
  --log-group-name-prefix /aws/bedrock-agentcore/runtimes
```

Delete a log group:

```bash
aws logs delete-log-group \
  --log-group-name /aws/bedrock-agentcore/runtimes/YOUR_RUNTIME_NAME
```

### Delete IAM roles created for the lab

List likely roles:

```bash
aws iam list-roles | grep Bedrock
aws iam list-roles | grep AgentCore
```

Before deleting a role, detach policies and remove inline policies:

```bash
aws iam list-attached-role-policies --role-name ROLE_NAME
aws iam detach-role-policy --role-name ROLE_NAME --policy-arn POLICY_ARN
aws iam list-role-policies --role-name ROLE_NAME
aws iam delete-role-policy --role-name ROLE_NAME --policy-name POLICY_NAME
aws iam delete-role --role-name ROLE_NAME
```

### Delete ECR repositories created by AgentCore builds

List repositories:

```bash
aws ecr describe-repositories
```

Delete the lab repository:

```bash
aws ecr delete-repository \
  --repository-name REPOSITORY_NAME \
  --force
```

### Stop the UI container

From `with_ui`:

```bash
docker compose down
```

## Troubleshooting

### Issue: Python version error

**Solution**: Ensure you have Python 3.13 or newer installed:

```bash
python --version
```

### Issue: Missing `GROQ_API_KEY`

**Solution**: Verify your `.env` file contains the key and is in the project root:

```bash
cat .env
```

### Issue: FAISS installation fails

**Solution**: Install the CPU version explicitly:

```bash
uv pip install --upgrade faiss-cpu
```

### Issue: AWS credentials not found

**Solution**: Configure AWS credentials using AWS CLI:

```bash
aws configure
```

### Issue: Error in CodeBuild

Configuration error:

```text
tool.setuptools.py-modules[0] must be python-module-name-relaxed
GIVEN VALUE: "02_bank_agent_agentcore_memory"
```

The value `02_bank_agent_agentcore_memory` is not allowed as a Python module name because Python package names cannot start with a number.

Rename the file/module references in:

```text
.bedrock_agentcore.yaml
pyproject.toml
```

Use a valid module name such as:

```text
bank_agent_agentcore_memory.py
```

### Rebuild the UI container

If the frontend or proxy changes do not appear:

```bash
docker compose down
docker compose build --no-cache
docker compose up
```
