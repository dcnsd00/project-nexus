
"""NEXUS integration catalogue. Configuration presence is not a successful connection."""
import os
CATALOG=[
("openai","OpenAI API","AI models and reasoning","OPENAI_API_KEY","configured_key_present","No automatic access to ChatGPT subscription or ChatGPT connectors."),
("binance","Binance public API","Market prices, order books, public exchange metadata",None,"public_endpoint","Read-only public endpoints; private account data requires separately authorized API credentials."),
("evm_rpc","EVM networks (Ethereum/Base/etc.)","Blocks, transactions, logs, contract reads","EVM_RPC_URL","endpoint_configured","No wallet signing or transaction submission."),
("bitcoin_rpc","Bitcoin Core","Blocks, UTXOs, transactions","BITCOIN_RPC_URL","endpoint_configured","Prefer local node or trusted read-only provider."),
("solana_rpc","Solana","Accounts, signatures, program data","SOLANA_RPC_URL","endpoint_configured","Read-only RPC."),
("acurast","Acurast","Node status and reward records","ACURAST_API_URL","endpoint_configured","Official documented API/export required."),
("grass","Grass","Account points and reward exports","GRASS_API_URL","endpoint_configured","Official documented API/export required."),
("aioz","AIOZ","DePIN node and public token data","AIOZ_API_URL","endpoint_configured","Official API/indexer required."),
("theta","Theta","Edge node and reward data","THETA_API_URL","endpoint_configured","Official documented API/export required."),
("wallet_watch","Public wallet watch","Token balances, NFTs, transactions","EVM_RPC_URL","endpoint_configured","Public addresses only; never request seed phrases."),
("nft","NFT metadata","ERC-721/1155 metadata, IPFS references","EVM_RPC_URL","endpoint_configured","Metadata is untrusted input; never execute embedded content."),
("ipfs","IPFS gateways","Fetch public content-addressed metadata","IPFS_GATEWAY","endpoint_configured","Read-only content retrieval."),
("coingecko","CoinGecko market data","Token prices and market metadata","COINGECKO_API_URL","endpoint_configured","Provider terms/rate limits apply."),
("open_banking","Open Banking","Bank account and transaction data","OPEN_BANKING_SANDBOX_URL","endpoint_configured","Sandbox first; real access requires regulated provider consent and OAuth."),
("github","GitHub","Repositories, commits, issues, releases","GITHUB_TOKEN","configured_key_present","Least-privilege token; repository permissions must be verified."),
("gitlab","GitLab","Projects, merge requests, pipelines","GITLAB_TOKEN","configured_key_present","Least-privilege token."),
("google_drive","Google Drive","Documents and project files","GOOGLE_OAUTH_CLIENT_ID","endpoint_configured","OAuth consent and scoped access required."),
("microsoft365","Microsoft 365","Outlook, OneDrive, SharePoint","MS_GRAPH_CLIENT_ID","endpoint_configured","OAuth consent and scoped access required."),
("telegram","Telegram Bot API","Alerts and command notifications","TELEGRAM_BOT_TOKEN","configured_key_present","Outbound notifications only until separately approved."),
("discord","Discord","Bot alerts and status channels","DISCORD_BOT_TOKEN","configured_key_present","Least-privilege bot permissions."),
("mqtt","MQTT / IoT","Telemetry from local nodes and devices","MQTT_BROKER_URL","endpoint_configured","No device control by default."),
("prometheus","Prometheus","Metrics, uptime and resource monitoring","PROMETHEUS_URL","endpoint_configured","Read-only metrics."),
("grafana","Grafana","Dashboards and monitoring","GRAFANA_URL","endpoint_configured","Read-only dashboards by default."),
("sage","SageMath","Advanced symbolic and computational mathematics","SAGE_EXECUTABLE","endpoint_configured","Local executable; structured operations only."),
("wolfram","Wolfram API","Specialized mathematics","WOLFRAM_APP_ID","configured_key_present","Optional paid/API access may apply."),
("alltrails","AllTrails","Trail data and routes","ALLTRAILS_API_URL","endpoint_configured","Only if an authorized API is available."),
]
def list_plugins():
 out=[]
 for pid,name,scope,env,kind,note in CATALOG:
  val=os.getenv(env,"").strip() if env else ""
  if kind=="public_endpoint": status="available_public_adapter_not_implemented"
  else: status="credential_present_adapter_pending" if val else "not_configured"
  out.append({"id":pid,"name":name,"scope":scope,"status":status,"configuration_variable":env,"security_note":note})
 return {"total":len(out),"connected":0,"policy":"read-only-first; no secrets are displayed; each write operation requires fresh owner approval","plugins":out}
