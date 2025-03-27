# Line Beacon Webhook

## Introduction

This project provides a webhook for handling events from **LINE Beacon**. It allows your application to receive and process real-time data when users interact with beacons via the **LINE Messaging API**.

This project is a part of the **INTERNET OF THINGS AND SMART SYSTEMS 11256030** course, focusing on **automatic attendance tracking** using **LINE Beacon** to notify users via LINE when they enter a room.

## Features

- Receive and process **LINE Beacon** events.
- Handle **enter** actions to track when users check into a room.
- Notify users when they enter a room.
- Retrieve user information, including their **LINE Display Name** when checking in.
- Allow users to customize their displayed name in the system, with the default being their **student ID**.
- Log and respond to webhook requests.
- Easy to deploy and integrate with your application.

## Installation

### 1. Clone the repository

Clone this repository from GitHub:

```bash
git clone https://github.com/T34M-WP/Line-beacon
cd Line-beacon
```

### 2. Install dependencies

Install the required packages using **pip**:

```bash
pip install -r requirements.txt
```

## Configuration

Before running the application, you need to set up environment variables:

- **LINE\_CHANNEL\_SECRET**: Your LINE channel secret.
- **LINE\_CHANNEL\_ACCESS\_TOKEN**: Your LINE channel access token.
- **WEBHOOK\_URL**: The public URL to receive webhook events.

You can set them in a `.env` file or export them manually:

```bash
export LINE_CHANNEL_SECRET="your_channel_secret"
export LINE_CHANNEL_ACCESS_TOKEN="your_access_token"
export WEBHOOK_URL="your_webhook_url"
```

## Usage

### Running the application

After installing the dependencies, you can start the application with the following command:

```bash
python app.py
```

The application will listen for **LINE Beacon** webhook events and respond accordingly.

## Deployment

For development and testing, you can expose your local server using **ngrok**:

1. Start your application:

```bash
python app.py
```

2. Run ngrok to create a public URL:

```bash
ngrok http 5000
```

3. Copy the generated **ngrok URL** and set it as your webhook in the **LINE Developers Console**:

```
https://your-ngrok-url/webhook
```

For production use, consider deploying the application on a cloud platform like **Heroku, AWS, or Google Cloud**.

## Setting Up in LINE Developers Console

To integrate this project with LINE, follow these steps:

### 1. Create a LINE Login Channel

1. Go to the [LINE Developers Console](https://developers.line.biz/).
2. Click **Create a new provider** (or use an existing one).
3. Under **Messaging API**, create a new **channel**.
4. Take note of your **Channel Secret** and **Channel Access Token** from the settings.

### 2. Enable LINE Beacon

1. In your **Messaging API** channel settings, go to the **LINE Beacon** section.
2. Enable **LINE Beacon** support.
3. Save your settings.

### 3. Set the Webhook URL

1. Navigate to the **Messaging API** settings.
2. Under **Webhook URL**, enter the public URL of your webhook endpoint, such as:
   ```
   https://your-ngrok-url/webhook
   ```
3. Click **Verify** to check if the webhook is responding correctly.
4. Enable the **Use webhook** option.

### 4. Deploy and Test

- Make sure your server is running and accessible via the webhook URL.
- Send a test **LINE Beacon** event by moving near a registered beacon.
- Check your logs to confirm the event is received.

## Webhook Endpoint

Make sure to configure your **LINE Developers Console** to point to your webhook URL:

```
https://your-domain.com/webhook
```
### Contributors

- **Warin Prompichai** ([GitHub Profile](https://github.com/T34M-WP))
- **Nutt Jangjit** ([GitHub Profile](https://github.com/NuttJJ))
  

