#!/bin/bash
set -e
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." &> /dev/null && pwd)"

URL="http://localhost:30080/thumbnails"
IMAGES=("$ROOT/test/images/original/")
THUMBNAILS=("$ROOT/test/images/thumbnail/")
JOBS=("$ROOT/test/jobs.txt")
mkdir -p "${THUMBNAILS}"
touch "$JOBS"
: > "$JOBS"

# Take max jobs from execution. eg "./test.sh 50", default 10 jobs
MAX_JOBS="${1:-10}"
#MAX_JOBS=300
COUNT=0

random_sleep() {
  awk 'BEGIN{srand(); printf "%.2f", 0.1 + rand()*0.9}'
}

while (( COUNT < MAX_JOBS )); do
    shopt -s nullglob
    for image in "${IMAGES}"/*.{jpg,jpeg,png,gif}; do
        (( COUNT >= MAX_JOBS )) && break

        [ -e $image ] || continue

        printf "${GREEN}Processing image: $image ...${NC}"
        # POST image to process to thumbnail
        RESPONSE=$(
            curl -X POST $URL \
            -H "Accept: application/json" \
            -F "file=@${image}"
            )
        echo $RESPONSE

        JOB_ID=$(awk -F'"' '{print $4}' <<< "$RESPONSE")
        [ -z "$JOB_ID" ] && continue
        echo "$JOB_ID" >> "$JOBS"

        # Download image after POST
        printf "${GREEN}Downloading thumbnail: $JOB_ID ...${NC}"
        RESPONSE=$(curl $URL"/$JOB_ID" \
        -H "Accept: application/json" \
        -o "${THUMBNAILS}/${JOB_ID}.jpg")
        echo $RESPONSE

        rm -f "${THUMBNAILS}/${JOB_ID}.jpg"  # Clean up

        sleep $(random_sleep)
        ((COUNT++))
    done
    shopt -u nullglob
done


