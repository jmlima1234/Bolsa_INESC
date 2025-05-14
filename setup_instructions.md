# Setting Up Pub/Sub and Agents

## Pub/Sub

1. Open a new terminal.

2. Activate archidetect environment and download dependencies (gcloud)
    
```bash
    cd archidetect
    source env/bin/activate
    pip install -r requirements.txt
    cd ..
```

3. Set environment variables for the pub/sub

```bash
    ## LINUX
    export PUBSUB_EMULATOR_HOST=localhost:8085
    export PUBSUB_PROJECT_ID="my-local-emulator-project"

    ## WINDOWS
    $env:PUBSUB_EMULATOR_HOST="localhost:8085"
    $env:PUBSUB_PROJECT_ID="my-local-emulator-project"

    ## MAC OS
    set PUBSUB_EMULATOR_HOST=localhost:8085
    set PUBSUB_PROJECT_ID="my-local-emulator-project"
```

4. Authenticate with your google cloud account

```bash
    gcloud auth application-default login
```

5. Start the pub/sub socket

```bash
    gcloud beta emulators pubsub start --project=my-local-emulator-project
```


## Strange

1. Open a new terminal.

2. Activate strange environment and download dependencies (gcloud)
    
```bash
    cd strange
    source venv/bin/activate
    pip install -r requirements.txt
```

3. Set environment variables for the pub/sub

```bash
    ## LINUX
    export PUBSUB_EMULATOR_HOST=localhost:8085
    export PUBSUB_PROJECT_ID="my-local-emulator-project"

    ## WINDOWS
    $env:PUBSUB_EMULATOR_HOST="localhost:8085"
    $env:PUBSUB_PROJECT_ID="my-local-emulator-project"

    ## MAC OS
    set PUBSUB_EMULATOR_HOST=localhost:8085
    set PUBSUB_PROJECT_ID="my-local-emulator-project"
```

4. Authenticate with your google cloud account

```bash
    gcloud auth application-default login
```

5. Join the pub/sub socket

```bash
    gcloud beta emulators pubsub env-init
```

6. Run the Strange server

```bash
    python3 manage.py runserver
```

## Archidetect

1. Open a new terminal.

2. Activate archidetect environment and download dependencies (gcloud)
    
```bash
    cd archidetect
    source env/bin/activate
    pip install -r requirements.txt
```

3. Set environment variables for the pub/sub

```bash
    ## LINUX
    export PUBSUB_EMULATOR_HOST=localhost:8085
    export PUBSUB_PROJECT_ID="my-local-emulator-project"

    ## WINDOWS
    $env:PUBSUB_EMULATOR_HOST="localhost:8085"
    $env:PUBSUB_PROJECT_ID="my-local-emulator-project"

    ## MAC OS
    set PUBSUB_EMULATOR_HOST=localhost:8085
    set PUBSUB_PROJECT_ID="my-local-emulator-project"
```

4. Authenticate with your google cloud account

```bash
    gcloud auth application-default login
```

5. Run Archidetect 

```bash
    cd api
    python3 archi_subscriber.py
```

## Frontend



1. Install server and dependencies

```bash
    cd frontend
    npm install
```

2. Run server

```bash
    npm start    
```
