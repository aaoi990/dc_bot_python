
from config import create_api
import tweepy
import re
import nltk
from nltk.corpus import stopwords
import itertools
import collections
import logging
from datetime import datetime, timedelta
import mysql.connector
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

class Bot:
    def __init__(self, keywords):
        self.api = create_api()
        self.cnx = mysql.connector.connect(
            user= os.getenv('DBUSER'),
            password=os.getenv("DATABASE_PASSWORD"),
            database= os.getenv('DATABASE'),
            host= os.getenv('DBHOST'))
        self.cursor = self.cnx.cursor()
        self.keywords = keywords
        self.stop_words = stopwords.words('english') 
        self._since = self.read_since_id()

    def __del__(self):
        self.cursor.close()
        self.cnx.close()

    @property
    def since(self):
        return self._since

    @since.setter
    def since(self, var):
        self._since = var

    @since.deleter
    def since(self):
        del self._since

    def init_db(self):
        self.cnx = mysql.connector.connect(
            user= os.getenv('DBUSER'),
            password=os.getenv("DATABASE_PASSWORD"),
            database= os.getenv('DATABASE'),
            host= os.getenv('DBHOST')
        )
        return self.cnx.cursor()

    def read_since_id(self):
        query = "SELECT since_id FROM since ORDER BY dtoi DESC LIMIT 1"
        self.cursor.execute(query)
        result_set = self.cursor.fetchall()
        return result_set[0][0]

    def write_since_id(self):
        self.cursor.execute("""INSERT INTO since (since_id, dtoi) 
            VALUES(%s, now()) ON DUPLICATE KEY UPDATE dtoi=now()""" % self.since)
        self.cnx.commit()

    def check_mentions(self):
        logger.info("Checking mentions since: %s" % self.since)
        new_since_id = self.since
        for tweet in tweepy.Cursor(self.api.mentions_timeline, self.since).items():
            new_since_id = max(tweet.id, new_since_id)
            if tweet.in_reply_to_status_id is not None:
                continue

            if any(keyword in tweet.text.lower() for keyword in self.keywords):
                try:
                    user = self.get_user_overview(tweet.entities['user_mentions'][1])
                except IndexError:
                    pass

                try:
                    user = self.examine_tweets(user)
                except:
                    pass

                self.compose_overview_reply(user, tweet)

        return new_since_id

    def remove_url(self, txt):
        return " ".join(re.sub("([^0-9A-Za-z \t])|(\w+:\/\/\S+)", "", txt).split())

    def examine_tweets(self, user):
        tweets = self.api.user_timeline(user['screen_name'],count=2000)
        all_tweets = [tweet.text for tweet in tweets]
        all_tweets_parse_url = [self.remove_url(tweet) for tweet in all_tweets]
        words_in_tweet = [tweet.lower().split() for tweet in all_tweets_parse_url]
        tweets_nsw = [[word for word in tweet_words if not word in self.stop_words]
              for tweet_words in words_in_tweet]
        all_words_nsw = list(itertools.chain(*tweets_nsw))
        counts_nsw = collections.Counter(all_words_nsw)
        print(counts_nsw.most_common(15))
        user['retweets'] = counts_nsw['rt']

        hashtags = []
        all_hash = [tweet.entities for tweet in tweets]
        for tweet in tweets:
            for hashtag in tweet.entities['hashtags']:
                hashtags.append(hashtag["text"])


        hashtags_pop = collections.Counter(hashtags)
        user['popular_hashtags'] = hashtags_pop.most_common(15)

        return user


    def get_user_overview(self, user):
        user_object = self.api.get_user(user['screen_name'])
        queried_account = {}
        queried_account['created'] = user_object.created_at
        queried_account['status_count'] = user_object.statuses_count
        queried_account['followers'] = user_object.followers_count
        queried_account['following'] = user_object.friends_count
        queried_account['verified'] = user_object.verified
        queried_account['screen_name'] = user['screen_name']
        queried_account['active'] = self.get_active_time(queried_account['created'])
        queried_account['average'] = self.get_average_tweets(queried_account['status_count'], queried_account['active'])

        return queried_account

    def get_active_time(self, date):
        a = datetime.now()
        b = date
        c = a - b
        return c.days

    def get_average_tweets(self, days, status):
        average = (days / status)
        return round(average, 2)

    def compose_overview_reply(self, user, tweet):
        logger.info("Answering to %s with overview tweet" % tweet.user.name)
        update = '@{} user {} was created: {}, Status count: {}, Average daily tweets: {}, Followers: {}, Following: {}, Retweets: {}'.format(
                tweet.user.screen_name,
                user['screen_name'],
                user['created'],
                user['status_count'],
                user['average'],
                user['followers'],
                user['following'],
                user['retweets'])
        logger.info(update)

        update_follow = '@{} Most used hashtags: {} '.format(tweet.user.screen_name,
                user['popular_hashtags'])
        logger.info(update_follow)
        #return self.api.update_status(
         #   status=update,
          #  in_reply_to_status_id=tweet.id)

