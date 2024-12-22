import tweepy
import requests
# the below import is for calculating date. Not needed for you but I needed it.
from datetime import date
import shutil, pathlib, os

# get params from environment variables
ACCESS_KEY = os.getenv("ACCESS_KEY", "")
ACCESS_SECRET = os.getenv("ACCESS_SECRET", "")
CONSUMER_KEY = os.getenv("CONSUMER_KEY", "")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET", "")
BEARER_TOKEN = os.getenv("BEARER_TOKEN", "")

Onion_API = "https://onion-web-api.onrender.com/api/news/list"
Detail_URL = "https://onion-agent.github.io/#/news/"

# this is the syntax for twitter API 2.0. It uses the client credentials that we created
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    access_token=ACCESS_KEY,
    access_token_secret=ACCESS_SECRET,
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
)

def get_news():
    # get last new from the Onion API
    response = requests.get(Onion_API)
    if response.status_code == 200:
        # Parse JSON data
        data = response.json()
        return data
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        print(response.text)

def create_tweet(data):

    # generate the tweet
    tweet = data['title']
    relay = "Details:" + "\n" + Detail_URL+data['slug']

    print(f"tweet: {tweet}")
    print(f"relay: {relay}")

    # create the tweet using the new api. Mention the image uploaded via the old api
    post_result = client.create_tweet(text=tweet)
    if post_result.errors:
        print(f"post_result: {post_result}")
        return post_result
    print(f"post_result: {post_result}")
    relay_result = client.create_tweet(text=relay, in_reply_to_tweet_id=post_result.data["id"])
    print(f"x_result: {relay_result}")
    return relay_result