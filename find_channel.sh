#!/bin/bash

# Retrieve Slack API token from environment variable
SLACK_API_TOKEN="${SLACK_API_TOKEN}"
CHANNEL_NAME="savteam"

# Check if the Slack API token is set
if [ -z "$SLACK_API_TOKEN" ]; then
    echo "Error: SLACK_API_TOKEN environment variable is not set."
    exit 1
fi

# Function to fetch channel list and extract the channel ID
fetch_channel_id() {
    local cursor=$1
    echo "Fetching channels list..." >&2

    response=$(curl -s -X GET "https://slack.com/api/conversations.list" \
        -H "Authorization: Bearer ${SLACK_API_TOKEN}" \
        -H "Content-Type: application/json" \
        -G \
        --data-urlencode "limit=100" \
        --data-urlencode "types=public_channel,private_channel" \
        $(if [ -n "$cursor" ]; then echo "--data-urlencode cursor=$cursor"; fi))

    if [ $? -ne 0 ]; then
        echo "Error: Failed to fetch channels list." >&2
        exit 1
    fi

    echo "Channels list fetched successfully." >&2

    # Extract channel with the given name and its ID
    echo "Searching for channel with name: $CHANNEL_NAME" >&2
    channel_id=$(echo "$response" | jq -r --arg CHANNEL_NAME "$CHANNEL_NAME" '.channels[] | select(.name == $CHANNEL_NAME) | .id')
    
    if [ -n "$channel_id" ]; then
        echo "Channel found: $CHANNEL_NAME, ID: $channel_id" >&2
        echo "$channel_id"
        return 0
    fi

    # Extract the next cursor for pagination
    next_cursor=$(echo "$response" | jq -r '.response_metadata.next_cursor')

    if [ -n "$next_cursor" ]; then
        echo "Next cursor found: $next_cursor. Fetching next page..." >&2
        fetch_channel_id "$next_cursor"
        return $?
    else
        echo "Channel not found." >&2
        return 1
    fi
}

# Initial call to fetch_channel_id without a cursor
fetch_channel_id ""
