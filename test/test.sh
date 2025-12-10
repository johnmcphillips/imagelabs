#!/bin/bash
set -e
GREEN='\033[0;32m'
NC='\033[0m'

URL="http://localhost:30080/thumbnails"
IMAGES=("./test/images/original/")
THUMBNAILS=("./test/images/thumbnail/")
JOBS=("./test/jobs.txt")
touch "$JOBS"
: > "$JOBS"

MAX_JOBS=25
COUNT=0

random_sleep() {
  awk 'BEGIN{srand(); printf "%.2f", 0.5 + rand()*0.9}'
}

while (( COUNT < MAX_JOBS )); do
    shopt -s nullglob
    for image in "${IMAGES}"/*.{jpg,jpeg,png,gif}; do
        (( COUNT >= MAX_JOBS )) && break

        [ -e $image ] || continue

        echo -e "${GREEN}Processing image: $image ...${NC}"
        # POST image to process to thumbnail
        RESPONSE=$(
            curl -X POST $URL \
            -H "Accept: application/json" \
            -F "file=@${image}"
            )
        echo "Response: $RESPONSE"

        JOB_ID=$(awk -F'"' '{print $4}' <<< "$RESPONSE")
        [ -z "$JOB_ID" ] && continue
        echo "$JOB_ID" >> "$JOBS"

        # Download image after POST
        echo -e "${GREEN}Downloading thumbnail: $JOB_ID ...${NC}"
        curl $URL"/$JOB_ID" \
        -H "Accept: application/json" \
        -o "${THUMBNAILS}/${JOB_ID}.jpg"

        sleep $(random_sleep)
        ((COUNT++))
    done
    shopt -u nullglob
done


