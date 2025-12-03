# ImageLabs
Thumbnail creation assignment

User can submit an image to an API endpoint. \
The API should:
- Save the original image
- Initiate long-running job to generate 100x100 thumbnail
- User recieves job ID as response

User should be able to:
- Check job status (processing, succeeded, failed)
- Fetch the thumbnail once succeeded
- List all submitted jobs
- Fetch debugging logs, metrics, monitoring


## Reasoning

## Architecture

## Setup
### TODO - Automate setup process

## Manual Setup
- Build the Python FastAPI services
```
docker build -t thumbnail-proc:latest .
```
- Create Kind Cluster
```
kind create cluster --name cogent --config kind-config.yaml
```
- Load Image
```
kind load docker-image thumbnail-proc:latest --name cogent
```
- Install Helm chart
```
helm upgrade --install thumbnail-proc ./helm/thumbnail-proc
```
- Port forward to svc
``` 
kubectl port-forward svc/thumbnail-proc-api 8080:8080
```
