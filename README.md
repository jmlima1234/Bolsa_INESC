# Bolsa_INESC

## APLens

For now, AP Lens only works alone.
To test AP Lens, 

```bash
cd mock_aplens
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./start_servers.sh
```

## Next steps

- Test if archidetect works alone too
- Create frontend to centralize action into Strange and make it orchestrate other 2 agents
- Change strange to talk through pub/sub with both agents
- GitHub agent
