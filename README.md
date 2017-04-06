# Introduction
The summarization algorithm operates on sentences, words, and named entities in a document extracted by the Rosette API.  Each sentence is assigned a score based on the contentful words and named entity mentions that occur in the sentence.  The score for each sentence is normalized by the length of the sentence in terms of the number of word tokens in the sentence.  Sentences are also penalized with a logarithmic falloff based on how close to the beginning of the document they occur (setences near the end of the document are penalized more than sentences toward the beginning).

## `summarize.py`
This script uses both the [`entities`](https://developer.rosette.com/features-and-functions#entity-extraction) and [`morphology/lemmas`](https://developer.rosette.com/features-and-functions#lemmas) endpoints to extract information about a document and uses that information to rank sentences by their content.  The script can then filter down to only the most contentful sentences to provide a gist of the original content.

### Installing Dependencies with Virtualenv
The script is written for Python 3.  If you are alright with installing external Python packages globally, you may skip this section.

You can install the dependencies using `virtualenv` so that you don't alter your global site packages.

The process for installing the dependencies using `virtualenv` is as follows for `bash` or similar shells:

Ensure your `virtualenv` is up to date.

    $ pip install -U virtualenv

**Note**: You may need to use `pip3` depending on your Python installation.

`cd` into the directory where the `summarize.py` script exists and create a Python virtual environment (this is the same location as this README):

    $ virtualenv .

Activate the virtual environment:

    $ source bin/activate

Once you've activated the virtual environment you can proceed to install the requirements safely without affecting your globabl site packages.

### Installing the Dependencies
You can install the dependencies via `pip` (or `pip3` depending on your installation of Python 3) as follows using the provided `requirements.txt`:

    $ pip install -r requirements.txt

### Usage
Once you've installed the dependencies you can run the script as follows:

    ./summarize.py -h
    usage: summarize.py [-h] [-i, INPUT] [-u] [-k KEY] [-a API_URL] [-l LANGUAGE]
                        [-p PERCENT] [-n TOP_N] [-v]

    Summarize a document based on content extracted via Rosette API

    optional arguments:
      -h, --help            show this help message and exit
      -i, INPUT, --input INPUT
                            Path to a plain-text file or URI (if no -i/--input
                            option is specified, input is read from stdin)
                            (default: None)
      -u, --content-uri     Specify that the input is a URI (otherwise load text
                            from file) (default: False)
      -k KEY, --key KEY     Rosette API Key (default: None)
      -a API_URL, --api-url API_URL
                            Alternative Rosette API URL (default:
                            https://api.rosette.com/rest/v1/)
      -l LANGUAGE, --language LANGUAGE
                            A three-letter (ISO 639-2 T) code that will override
                            automatic language detection (default: None)
      -p PERCENT, --percent PERCENT
                            What percentage of the original sentences to keep
                            (default: 0.15)
      -n TOP_N, --top-n TOP_N
                            How many of the original sentences to keep (overrides
                            -p/--percent) (default: None)
      -v, --verbose         Get the full ADM with summarization info as JSON
                            (default: False)
### Example
If you have a plain-text document you wish to summarize, you can do so with:

    $ ./summarize.py -k $ROSETTE_USER_KEY -i path/to/your/file.txt

You can summarize a document via a URI as follows (the content of the URI will be automaticaly extracted via the Rosette API):

    $ ./summarize.py -k $ROSETTE_USER_KEY -u -i "http://www.csmonitor.com/Science/2016/1209/How-dust-changed-scientists-view-of-Saturn-s-C-ring"

For the above example, the document is rather long, and the default summarization will reduce the document to 50% of its original length (in terms of sentences).  You can specify a different percentage with the `-p/--percent` option, or specify a particular numer of sentences with the `-n/--top-n` option.

For example, to limit the summary to ten sentences:

    $ ./summarize.py -k $ROSETTE_USER_KEY -u -i "http://www.csmonitor.com/Science/2016/1209/How-dust-changed-scientists-view-of-Saturn-s-C-ring" -n 10
    The secret to understanding Saturn's C ring? 
    Saturn's icy moon Mimas is dwarfed by the planet's enormous rings.
    Scientists at Cornell University in Ithaca, N.Y., have been using data from NASA’s Cassini mission to Saturn, particularly its microwave passive radiometer, to study the planet’s rings. 
    The rings are mostly composed of ice, but “it is the small fraction of non-icy material – the dust the ring collects – that is valuable for clues about the ring’s origin and age,” doctoral candidate Zhimeng Zhang, who led the work, told the Cornell Chronicle.
    Dust drifts through space from beyond the Kuiper Belt and hits Saturn’s rings. 
    The older a ring is, therefore, the more dust it will have time to collect. 
    And scientists can analyze the dust to figure out how old the ring is.
    It collides with Saturn’s rings, and sticks to them. 
    Zhang and her fellow researchers believe that the C ring has been “continuously polluted” by these space dust particles.
    When instruments like Cassini’s microwave passive radiometer measure a ring’s thermal emissions, dustier rings will have higher readings. 

You can also enable the `-v/--verbose` option which outputs results as an Annotated Data Model (ADM).  The ADM has a `summary` attribute that contains the summarization information including the rank scores for each sentence, which are intended to indicate how contentful each sentence is:

    ./summarize.py -k $ROSETTE_USER_KEY -u -i "http://www.csmonitor.com/Science/2016/1209/How-dust-changed-scientists-view-of-Saturn-s-C-ring" -n 10 -v | jq .attributes.summary
    {
      "ranked": [
        {
          "startOffset": 0,
          "endOffset": 45,
          "text": "The secret to understanding Saturn's C ring? ",
          "score": 29.100689277811085,
          "tokenLength": 9
        },
        ...,
        {
          "startOffset": 3199,
          "endOffset": 3205,
          "text": "Daily",
          "score": 0,
          "tokenLength": 0
        }
      ],
      "summary": "The secret to understanding Saturn's C ring? \nSaturn's icy moon Mimas is dwarfed by the planet's enormous rings.\nScientists at Cornell University in Ithaca, N.Y., have been using data from NASA’s Cassini mission to Saturn, particularly its microwave passive radiometer, to study the planet’s rings. \nThe rings are mostly composed of ice, but “it is the small fraction of non-icy material – the dust the ring collects – that is valuable for clues about the ring’s origin and age,” doctoral candidate Zhimeng Zhang, who led the work, told the Cornell Chronicle.\nDust drifts through space from beyond the Kuiper Belt and hits Saturn’s rings. \nThe older a ring is, therefore, the more dust it will have time to collect. \nAnd scientists can analyze the dust to figure out how old the ring is.\nIt collides with Saturn’s rings, and sticks to them. \nZhang and her fellow researchers believe that the C ring has been “continuously polluted” by these space dust particles.\nWhen instruments like Cassini’s microwave passive radiometer measure a ring’s thermal emissions, dustier rings will have higher readings. ",
      "info": "maintained 10 sentences (27% of original sentences)"
    }
