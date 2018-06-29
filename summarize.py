#!/usr/bin/env python3

"""Summarize a document based on content extracted via Rosette API"""

import json
import os
import sys
import urllib

from collections import Counter
from getpass import getpass
from math import log
from operator import itemgetter, methodcaller

EXTERNALS = 'argparse', 'rosette_api'
try:
    import argparse
    from rosette.api import API, DocumentParameters
except ImportError:
    message = '''This script depends on the following modules:
    {}
If you are missing any of these modules, install them with pip3:
    $ pip3 install {}'''
    print(
        message.format('\n\t'.join(EXTERNALS), ' '.join(EXTERNALS)),
        file=sys.stderr
    )
    sys.exit(1)

DEFAULT_ROSETTE_API_URL = 'https://api.rosette.com/rest/v1/'

CONTENTFUL_POS_TAGS = {
    # see https://developer.rosette.com/features-and-functions#parts-of-speech
    'ADJ',
    'ADV',
    'NOUN',
    'PROPN',
    'VERB'
    # for reference, other possible POS tags:
    #'ADP',
    #'AUX',
    #'CONJ',
    #'DET',
    #'INTJ',
    #'NUM',
    #'PART',
    #'PRON',
    #'PUNCT',
    #'SCONJ',
    #'SYM',
    #'X'
}

CONTENTFUL_ENTITY_TYPES = {
    # see https://developer.rosette.com/features-and-functions#-entity-types
    'IDENTIFIER:DISTANCE',
    'IDENTIFIER:LATITUDE_LONGITUDE',
    'IDENTIFIER:MONEY',
    'LOCATION',
    'NATIONALITY',
    'ORGANIZATION',
    'PERSON',
    'PRODUCT',
    'RELIGION',
    'TEMPORAL:DATE',
    'TITLE'
    # for reference, other possible entity types:
    #'IDENTIFIER:CREDIT_CARD_NUM',
    #'IDENTIFIER:EMAIL',
    #'IDENTIFIER:PERSONAL_ID_NUM',
    #'IDENTIFIER:PHONE_NUMBER',
    #'IDENTIFIER:URL',
    #'TEMPORAL:TIME',
}

def extent(obj):
    """Get the start and end offset attributes of a dict-like object

    a = {'startOffset': 0, 'endOffset': 5}
    b = {'startOffset': 0, 'endOffset': 10}
    c = {'startOffset': 5, 'endOffset': 10}

    extent(a) -> (0, 5)
    extent(b) -> (0, 10)
    extent(c) -> (5, 10)
    extent({}) -> (-1, -1)

    """
    return obj.get('startOffset', -1), obj.get('endOffset', -1)

def overlaps(*objs):
    """Find character offsets that overlap between objects

    a = {'startOffset': 0, 'endOffset': 5}
    b = {'startOffset': 0, 'endOffset': 10}
    c = {'startOffset': 5, 'endOffset': 10}

    overlaps(a, b) -> {0, 1, 2, 3, 4}
    bool(overlaps(a, b)) -> True

    overlaps(b, c) -> {5, 6, 7, 8, 9}
    bool(overlaps(b, c)) -> True

    overlaps(a, c) -> set()
    bool(overlaps(a, c)) -> False

    """
    return set.intersection(*(set(range(*extent(obj))) for obj in objs))

def get_content(content, uri=False):
    """Load content from file or stdin"""
    if content is None:
        content = sys.stdin.read()
    elif os.path.isfile(content):
        with open(content, mode='r') as f:
            content = f.read()
    # Rosette API may balk at non-Latin characters in a URI so we can get urllib
    # to %-escape the URI for us
    if uri:
        unquoted = urllib.parse.unquote(content)
        content = urllib.parse.quote(unquoted, '/:')
    return content

def entity_mentions(adm):
    """Generate named entity mentions from an ADM (Annotated Data Model)"""
    for entity in adm['attributes']['entities']['items']:
        for mention in entity['mentions']:
            # Augment mentions with the entity type of the entity they refer to
            mention['type'] = entity.get('type')
            yield mention

def request(content, endpoint, api, language=None, uri=False, **kwargs):
    """Request Rosette API results for the given content and endpoint.

    This method gets the requested results as an A(nnotated) D(ata) M(odel) or 
    ADM. An ADM is a Python dict representing a document content, annotations of
    the document content, and metadata.

    content:  path or URI of a document for the Rosette API to process
    endpoint: a Rosette API endpoint string (e.g., 'entities')
              (see https://developer.rosette.com/features-and-functions)
    api:      a rosette.api.API instance
              (e.g., API(user_key=<key>, service_url=<url>))
    language: an optional ISO 639-2 T language code
              (the Rosette API will automatically detect the language of the
              content by default)
    uri:      specify that the content is to be treated as a URI and the
              the document content is to be extracted from the URI
    kwargs:   additional keyword arguments
              (e.g., if endpoint is 'morphology' you can specify facet='lemmas';
              see https://developer.rosette.com/features-and-functions for
              complete documentation)
    
    For example:
    
    api = API(user_key=<key>, service_url=DEFAULT_ROSETTE_API_URL)
    
    result = request('George Washington', 'entities', api)
    result['entities] -> [
        {
            'count': 1,
            'entityId': 'Q23',
            'mention': 'George Washington',
            'normalized': 'George Washington',
            'type': 'PERSON'
        }
    ]
    
    result = request('This is an example.', 'morphology', api, facet='lemmas')
    result['lemmas'] -> ['this', 'be', 'an', 'example', '.']
    
    # Request ADM result output format
    api.set_url_parameter('output', 'rosette') 
    result = request('George Washington', 'entities', api)
    result['attributes]['entities'] -> {
        'itemType': 'entities',
        'items': [
            {
                'confidence': 0.15023640729196142,
                'entityId': 'Q23',
                'headMentionIndex': 0,
                'mentions': [
                    {
                        'endOffset': 17,
                        'normalized': 'George Washington',
                        'source': 'statistical',
                        'startOffset': 0,
                        'subsource': '/data/roots/rex/data/statistical/eng/model_uc-LE.bin'
                    }],
                'type': 'PERSON'
            }
        ],
        'type': 'list'
    }
    
    """
    parameters = DocumentParameters()
    if uri:
        parameters['contentUri'] = content
    else:
        parameters['content'] = content
    parameters['language'] = language
    adm = methodcaller(endpoint, parameters, **kwargs)(api)
    return adm

def get_adm(content, api, language=None, uri=False):
    """Get a single ADM result with combined entities and lemmatization
    
    For example:
    
    api = API(user_key=<key>, service_url='https://api.rosette.com/rest/v1/')
    
    adm = get_adm('George Washington was the first president of the U.S.', api)
    
    adm['attributes']['entities']['items'] -> [
        {
            "mentions": [
                {
                    "endOffset": 17,
                    "subsource": "/data/roots/rex/data/statistical/eng/model_uc-LE.bin",
                    "startOffset": 0,
                    "normalized": "George Washington",
                    "source": "statistical"
                }
            ],
            "confidence": 0.23607198500778653,
            "headMentionIndex": 0,
            "entityId": "Q23",
            "type": "PERSON"
        },
        {
            "mentions": [
                {
                    "endOffset": 41,
                    "subsource": "/data/roots/rex/data/statistical/eng/model_uc-LE.bin",
                    "startOffset": 32,
                    "normalized": "president",
                    "source": "statistical"
                }
            ],
            "headMentionIndex": 0,
            "entityId": "T1",
            "type": "TITLE"
        },
        {
            "mentions": [
                {
                    "endOffset": 53,
                    "subsource": "/data/roots/rex/data/gazetteer/eng/accept/gaz-LE.bin",
                    "startOffset": 49,
                    "normalized": "U.S.",
                    "source": "gazetteer"
                }
            ],
            "confidence": 0.08225596587583098,
            "headMentionIndex": 0,
            "entityId": "Q30",
            "type": "LOCATION"
        }
    ]
    
    adm['attributes']['token']['items'] -> [
        {
            "endOffset": 6,
            "text": "George",
            "analyses": [
                {
                    "partOfSpeech": "PROPN",
                    "lemma": "George",
                    "raw": "George[+Prop][+Fem][+PROP]"
                },
                {
                    "partOfSpeech": "PROPN",
                    "lemma": "George",
                    "raw": "George[+Prop][+Masc][+PROP]"
                },
                {
                    "partOfSpeech": "PROPN",
                    "lemma": "George",
                    "raw": "George[+Prop][+Fam][+PROP]"
                }
            ],
            "startOffset": 0
        },
        {
            "endOffset": 17,
            "text": "Washington",
            "analyses": [
                {
                    "partOfSpeech": "PROPN",
                    "lemma": "Washington",
                    "raw": "Washington[+Prop][+Place][+City][+PROP]"
                },
                {
                    "partOfSpeech": "PROPN",
                    "lemma": "Washington",
                    "raw": "Washington[+Prop][+Place][+PROP]"
                },
                {
                    "partOfSpeech": "PROPN",
                    "lemma": "Washington",
                    "raw": "Washington[+Prop][+Place][+Misc][+PROP]"
                },
                {
                    "partOfSpeech": "PROPN",
                    "lemma": "Washington",
                    "raw": "Washington[+Prop][+Fam][+PROP]"
                },
                {
                    "partOfSpeech": "PROPN",
                    "lemma": "Washington",
                    "raw": "Washington[+Prop][+Masc][+PROP]"
                }
            ],
            "startOffset": 7
        },
        {
            "endOffset": 21,
            "text": "was",
            "analyses": [
                {
                    "partOfSpeech": "VERB",
                    "lemma": "be",
                    "raw": "be[+VBPAST]"
                }
            ],
            "startOffset": 18
        },
        {
            "endOffset": 25,
            "text": "the",
            "analyses": [
                {
                    "partOfSpeech": "DET",
                    "lemma": "the",
                    "raw": "the[+DET]"
                }
            ],
            "startOffset": 22
        },
        {
            "endOffset": 31,
            "text": "first",
            "analyses": [
                {
                    "partOfSpeech": "ADJ",
                    "lemma": "one",
                    "raw": "one[+ORD]"
                }
            ],
            "startOffset": 26
        },
        {
            "endOffset": 41,
            "text": "president",
            "analyses": [
                {
                    "partOfSpeech": "NOUN",
                    "lemma": "president",
                    "raw": "president[+NOUN]"
                }
            ],
            "startOffset": 32
        },
        {
            "endOffset": 44,
            "text": "of",
            "analyses": [
                {
                    "partOfSpeech": "ADP",
                    "lemma": "of",
                    "raw": "of[+PREP]"
                }
            ],
            "startOffset": 42
        },
        {
            "endOffset": 48,
            "text": "the",
            "analyses": [
                {
                    "partOfSpeech": "DET",
                    "lemma": "the",
                    "raw": "the[+DET]"
                }
            ],
            "startOffset": 45
        },
        {
            "endOffset": 53,
            "text": "U.S.",
            "analyses": [
                {
                    "partOfSpeech": "PROPN",
                    "lemma": "U.S.",
                    "raw": "U.S.[+Prop][+Place][+Country][+PROP]"
                }
            ],
            "startOffset": 49
        }
    ]
    
    """
    # get results as ADM
    api.set_url_parameter('output', 'rosette')
    # make the request for entities
    adm = request(content, 'entities', api, language=language, uri=uri)
    # make separate request for lemmas
    lemmas_adm = request(content, 'morphology', api, language, uri=uri, facet='lemmas')
    # combine the results into a single ADM
    adm['attributes']['token'].update(lemmas_adm['attributes']['token'])
    return adm

def analysis(token):
    """Get the first analysis of a token
    
    token = {
        "endOffset": 4,
        "text": "will",
        "analyses": [
            {
                "partOfSpeech": "AUX",
                "lemma": "will",
                "raw": "will[+VAUX]"
            },
            {
                "partOfSpeech": "VERB",
                "lemma": "will",
                "raw": "will[+VI]"
            },
            {
                "partOfSpeech": "VERB",
                "lemma": "will",
                "raw": "will[+VPRES]"
            },
            {
                "partOfSpeech": "NOUN",
                "lemma": "will",
                "raw": "will[+NOUN]"
            }
        ],
        "startOffset": 0
    }
    
    analysis(token) -> {
        'partOfSpeech': 'AUX',
        'lemma': 'will',
        'raw': 'will[+VAUX]'
    }
    """
    return token.get('analyses', [{}])[0]

def token_key(token):
    """Get the raw, morphological analaysis of a token or lemma/POS"""
    morphotagged = analysis(token).get('raw')
    lemma_pos = (analysis(token).get('lemma'), analysis(token).get('partOfSpeech'))
    return morphotagged or lemma_pos

def entity_key(mention):
    """Get the entity identifier of the entity mention"""
    return mention.get('entityId')

def lemma_fd(adm):
    """Get a frequency distribution of contentful lemmas from an ADM
    
    Frequencies are counted based on tokens' raw, morphological analyses or 
    their lemma/POS if the morphological analysis isn't available.
    
    """
    def is_contentful(token):
        return analysis(token).get('partOfSpeech') in CONTENTFUL_POS_TAGS
    tokens = adm['attributes']['token']['items']
    return Counter(token_key(t) for t in tokens if is_contentful(t))

def entity_fd(adm):
    """Get a frequency distribution of contentful named entities from an ADM
    
    Frequencies are counted based on entities' identifiers.
    
    """
    def is_contentful(mention):
        return mention.get('type') in CONTENTFUL_ENTITY_TYPES
    mentions = entity_mentions(adm)
    return Counter(entity_key(m) for m in mentions if is_contentful(m))

def score(item, fd, key):
    """Assign a score to an item based based on a frequency distribution
    
    item: something counted in a frequency distribution based on a key
    fd:   a frequency distribution (an instance of collections.Counter)
    key:  a method that returns a key value in the frequency distribution
          a key method must return a hashable value
    
    """
    return fd.get(key(item), 0)

def get_text(adm, obj):
    """Recover the text of an object based on its character offsets
    
    adm["data"] -> "The secret to understanding Saturn's C ring?"
    obj = {
        "startOffset" : 28,
        "endOffset": 34
    }
    get_text(adm, obj) -> "Saturn"
    
    """
    return adm['data'][slice(*extent(obj))]

def score_sentences(adm):
    """Assign a score and token-length to each sentence in an ADM
    
    A higher scores indicates a sentence that is more contentful.  The ADM is 
    modified in-place.
    
    adm["attributes"]["sentence"]["items"][0].keys() -> [
        "startOffset",
        "endOffset"
    ]
    score_sentences(adm) -> None
    adm["attributes"]["sentence"]["items"][0].keys() -> [
        "startOffset",
        "endOffset",
        "score",
        "tokenLength"
    ]
    
    """
    lemma_frequencies = lemma_fd(adm)
    entity_frequencies = entity_fd(adm)
    sentences = adm['attributes']['sentence']['items']
    tokens = sorted(adm['attributes']['token']['items'], key=extent)
    mentions = sorted(entity_mentions(adm), key=extent)
    for i, sentence in enumerate(sentences):
        sentence['score'] = 0.0
        sentence['tokenLength'] = 0
        token = tokens.pop(0) if tokens else {}
        mention = mentions.pop(0) if mentions else {}
        # frequencies of contentful tokens inscrease the sentence the score
        while overlaps(token, sentence):
            sentence['score'] += score(token, lemma_frequencies, token_key)
            token = tokens.pop(0) if tokens else {}
            sentence['tokenLength'] += 1
        # frequencies of contentful entity mentions contribute to the score
        while overlaps(mention, sentence):
            sentence['score'] += score(mention, entity_frequencies, entity_key)
            mention = mentions.pop(0) if mentions else {}
        # normalize sentence score by sentence length
        sentence['score'] /= max(sentence['tokenLength'], 1)
        # penalize later sentences in the document based on their position
        # (sentences that occur later in a document get penalized more but with 
        # logarithmic falloff)
        sentence['score'] *= log(len(sentences) - i + 1)

def summarize(adm, summarize_percent, n=None):
    """Augment an ADM with a summary attribute
    
    Each sentence is scored then ranked based on its content.  Only the top N
    sentences (or top %) are retained in the summary, but each sentence is 
    ranked by its score in adm["attributes"]["summary"]["ranked"].  The ADM is
    modified in-place.
    
    adm:               ADM that has been annotated for named entities and lemmas
    summarize_percent: What percentage of the document to retain
                       E.g., 0.5 would retain 50% of the sentences.
    n:                 Include only the top n sentences. E.g., 10 would specify 
                       that only the top 10 highest ranked sentences should be 
                       included in the summary. This option will override 
                       summarize_percent if specified.
    
    adm["attributes"].keys() -> [
        "entities",
        "languageDetection",
        "scriptRegion",
        "sentence",
        "token"
    ]
    summarize(adm, 0.5, None) -> None
    adm["attributes"].keys() -> [
        "entities",
        "languageDetection",
        "scriptRegion",
        "sentence",
        "token",
        "summary
    ]
    adm["attributes"]["summary"].keys() -> [
        "info",
        "ranked",
        "summary"
    ]
    
    """
    score_sentences(adm)
    sentences = adm['attributes']['sentence']['items']
    if n is None:
        n = max(int(len(sentences) * summarize_percent), 1)
    else:
        summarize_percent = n / len(sentences)
    info = 'maintained {} sentences ({:0.0%} of original sentences)'
    ranked = sorted(sentences, key=itemgetter('score'), reverse=True)
    for sentence in ranked:
        sentence['text'] = get_text(adm, sentence)
    top_n = sorted(ranked[:n], key=extent)
    summary = '\n'.join(sentence['text'].rstrip('\r\n') for sentence in top_n)
    adm['attributes']['summary'] = {
        'info': info.format(n, summarize_percent),
        'ranked': ranked,
        'summary': summary
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__
    )
    parser.add_argument(
        '-i,',
        '--input',
        help='Path to a plain-text file or URI (if no -i/--input option is specified, input is read from stdin)',
        default=None
    )
    parser.add_argument(
        '-u',
        '--content-uri',
        action='store_true',
        help='Specify that the input is a URI (otherwise load text from file)'
    )
    parser.add_argument(
        '-k',
        '--key',
        help='Rosette API Key',
        default=None
    )
    parser.add_argument(
        '-a',
        '--api-url',
        help='Alternative Rosette API URL',
        default=DEFAULT_ROSETTE_API_URL
    )
    parser.add_argument(
        '-l',
        '--language',
        help='A three-letter (ISO 639-2 T) code that will override automatic language detection',
        default=None
    )
    parser.add_argument(
        '-p',
        '--percent',
        type=float,
        help='What percentage of the original sentences to keep',
        default=0.15
    )
    parser.add_argument(
        '-n',
        '--top-n',
        type=int,
        help='How many of the original sentences to keep (overrides -p/--percent)',
        default=None
    )
    parser.add_argument(
        '-v',
        '--verbose',
        help='Get the full ADM with summarization info as JSON',
        action='store_true'
    )
    args = parser.parse_args()
    # Get the user's Rosette API key
    key = args.key or getpass(prompt='Enter your Rosette API key: ')
    # Instantiate the Rosette API
    api = API(user_key=key, service_url=args.api_url)
    # Load content from file path, URI, or stdin
    content = get_content(args.input, args.content_uri)
    # Get the ADM result
    adm = get_adm(content, api, args.language, args.content_uri)
    # Perform summarization on the ADM
    summarize(adm, args.percent, args.top_n)
    if args.verbose:
        print(json.dumps(adm, ensure_ascii=False))
    else:
        print(adm['attributes']['summary']['summary'])
