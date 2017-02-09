import json
import logging
import re
import requests
from string import Template

logger = logging.getLogger(__name__)

# Stuff brought in from original casebot
CL_URL_TEMPLATE = Template("https://www.courtlistener.com/c/$reporter/$volume/$page/")
CL_FIND_URL_TEMPLATE = Template("https://www.courtlistener.com/api/rest/v3/search/?format=json&q=casename%3A($query)")
MINIMUM_VIABLE_CITATION_PATTERN = r"^(\d+)\s([A-Za-z0-9.\s]+)\s(\d+)$"
FIND_PATTERN = r"find\s+(.+)$"
FIND_RE = re.compile(FIND_PATTERN)

def handle_find(query):
    """
    The `find` command searches CourtListener by case name.
    https://github.com/anseljh/casebot/issues/3
    """
    # global config

    reply = None

    url = CL_FIND_URL_TEMPLATE.substitute({'query': query})
    request_headers = {'user-agent': config['General']['user_agent']}

    # Authenticate to CourtListener using token
    # https://github.com/anseljh/casebot/issues/7
    cl_token = config.get('CourtListener').get('courtlistener_token')
    # if cl_token is not None:
    #     request_headers['Authenticate'] = 'Token ' + cl_token
    #     print("Added CL Authentication Token header")
    response = requests.get(url, headers=request_headers)

    # Give some output on stdout
    logger.debug(response)
    logger.debug(response.headers)
    logger.debug(response.url)

    # Convert from JSON
    response_data = response.json()

    hits = response_data.get('count')
    if hits > 0:
        first = response_data.get('results')[0]
        logger.debug(first)
        url = "https://www.courtlistener.com" + first.get('absolute_url')
        logger.debug(url)
        name = first.get('caseName')
        logger.debug(name)
        year = first.get('dateFiled')[:4]
        logger.debug(year)
        citation = first.get('citation')[0]
        logger.debug(citation)
        court = first.get('court_citation_string')
        logger.debug(court)

        # msg = "CourtListener had %d hits for the query `%s`. Here's the first:\n"
        # if court != 'SCOTUS':
        #     message.reply(msg + "%s, %s (%s %s)\n%s" % (hits, query, name, citation, court, year, url))
        # else:
        #     message.reply(msg + "%s, %s (%s)\n%s" % (hits, query, name, citation, year, url))

        if court != 'SCOTUS':
            reply = "%s, %s (%s %s)\n%s" % (name, citation, court, year, url)
        else:
            reply = "%s, %s (%s)\n%s" % (name, citation, year, url)
    else:
        reply = "CourtListener had zero results for the query `%s`" % (query)
    return reply

def handle_citation(message, volume=None, reporter=None, page=None):
    # global config

    reply = None

    # Look up using CourtListener /c tool
    mapping = {'volume': volume, 'reporter': reporter, 'page': page}
    url = CL_URL_TEMPLATE.substitute(mapping)
    request_headers = {'user-agent': config['General']['user_agent']}
    response = requests.get(url, headers=request_headers)

    # Give some output on stdout
    logger.debug(response)
    logger.debug(response.headers)
    logger.debug(response.url)

    # Send the message!
    if response.status_code == 404:
        reply = "Sorry, I can't find that citation in CourtListener."
    else:
        reply = response.url
    return reply


class RtmEventHandler(object):
    def __init__(self, slack_clients, msg_writer):
        self.clients = slack_clients
        self.msg_writer = msg_writer

    def handle(self, event):

        if 'type' in event:
            self._handle_by_type(event['type'], event)

    def _handle_by_type(self, event_type, event):
        # See https://api.slack.com/rtm for a full list of events
        if event_type == 'error':
            # error
            self.msg_writer.write_error(event['channel'], json.dumps(event))
        elif event_type == 'message':
            # message was sent to channel
            self._handle_message(event)
        elif event_type == 'channel_joined':
            # you joined a channel
            self.msg_writer.write_help_message(event['channel'])
        elif event_type == 'group_joined':
            # you joined a private group
            self.msg_writer.write_help_message(event['channel'])
        else:
            pass

    def _handle_message(self, event):
        # Filter out messages from the bot itself, and from non-users (eg. webhooks)
        if ('user' in event) and (not self.clients.is_message_from_me(event['user'])):

            msg_txt = event['text']

            if self.clients.is_bot_mention(msg_txt) or self._is_direct_message(event['channel']):
                # e.g. user typed: "@pybot tell me a joke!"
                if 'help' in msg_txt:
                    self.msg_writer.write_help_message(event['channel'])
                elif re.search('hi|hey|hello|howdy', msg_txt):
                    self.msg_writer.write_greeting(event['channel'], event['user'])
                # elif 'joke' in msg_txt:
                #     self.msg_writer.write_joke(event['channel'])
                elif 'attachment' in msg_txt:
                    self.msg_writer.demo_attachment(event['channel'])
                elif 'echo' in msg_txt:
                    self.msg_writer.send_message(event['channel'], msg_txt)
                elif msg_txt.startswith('find'):
                    find_re_result = FIND_RE.search(msg_txt)
                    if find_re_result:
                        query = find_re_result.group(1)
                        find_result = handle_find(query)
                        if find_resul:
                            self.msg_writer.send_message(event['channel'], find_result)
                        else:
                            logger.debug("No matches for query: %s" % (query))
                    else:
                        logger.error("Nothing for find_re_result!")
                        self.msg_writer.send_message(event['channel'], "Does not compute.")
                else:
                    self.msg_writer.write_prompt(event['channel'])

    def _is_direct_message(self, channel):
        """Check if channel is a direct message channel

        Args:
            channel (str): Channel in which a message was received
        """
        return channel.startswith('D')
