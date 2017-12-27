#!/usr/bin/env python
from __future__ import print_function
import re
import logging
import sys
import os
import codecs

from ycmd.completers.completer import Completer
from ycmd import responses
from ycmd import utils
from ycmd import identifier_utils

identifier_utils.FILETYPE_TO_IDENTIFIER_REGEX['tex'] = re.compile( r"(?:\\[@a-zA-Z]+)|(?:\{[_\w:-]*\}?)|(?:\[[_\w:-]*\]?)")

def Update_RegEx( new ):
    identifier_utils.FILETYPE_TO_IDENTIFIER_REGEX['tex'] = re.compile ( new , re.U )
    return True

# To handle BibTeX properly
nobibparser = False
try:
    import bibtexparser
    from bibtexparser.bparser import BibTexParser
    from bibtexparser.customization import convert_to_unicode, author
except ImportError:
    nobibparser = True

def smart_truncate(content, length=30, suffix='...'):
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length+1-len(suffix)].split(' ')[0:-1]) + suffix

def bib_customizations(record):
    def truncate_title(record):
        title = record['title'] if 'title' in record else ''
        title = smart_truncate(title)
        record['title'] = title
        return record

    def et_al(record):
        author = record['author'] if 'author' in record else []
        author = [a.replace(', ', ' ').replace(',', ' ') for a in author]
        if len(author) == 0:
            record['author'] = ''
        elif len(author) == 1:
            record['author'] = author[0]
        else:
            record['author'] = author[0] + ' et al.'
        return record

    record = convert_to_unicode(record)
    record = author(record)
    record = et_al(record)
    record = truncate_title(record)
    return record

LOG = logging.getLogger(__name__)

class GenericSlave (object):
    """
    A generic slave for completing. Contains its own conception of
    the main directory, and its own responses cache
    """
    def __init__(self, output):
        self._completion_target = 'none'
        self._main_directory    = None
        self.completion_wanted  = False
        self._files             = {}
        self._cached_data       = {}
        self._d_cache_hits      = 0
        self._goto_labels       = {}
        self.extensions         = ''
        self.output_regex       = re.compile(output + "$", re.UNICODE)

    def ShouldUse(self, target, request_data):
        """
        Returns true if it's meant to give a completion, and sets
        our internal truth flag
        """
        if self._main_directory is None:
            self._ComputeMainDirectory(request_data)

        match = self.output_regex.search(target)
        if  match is not None:
            self.completion_wanted = True
        else:
            self.completion_wanted = False
        return self.completion_wanted


    def _Walk( self, path, what ):
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(what):
                    yield os.path.join(root, file)

    def _ComputeMainDirectory( self,  request_data ):
        def FindMain(path, what):
            found = False
            for file in os.listdir(path):
                if file.endswith(what):
                    self._main_directory = path
                    found = True
                    break

            if not found:
                new_path = os.path.dirname(os.path.normpath(path))
                if new_path == path or new_path == "":
                    return False
                else:
                    return FindMain(new_path, what)
            return True

        filepath = request_data['filepath']
        path     = os.path.dirname(filepath)

        if not FindMain(path, self.extensions):
            self._main_directory = filepath
            print("Unable to set the main directory...", sys.stderr)
        else:
            print("Main directory successfully found at {}".format(self._main_directory), 
                    sys.stderr)

    def _CacheDataAndSkip(self, filename):
        last_modification = os.path.getmtime(filename)

        if filename not in self._files:
            self._files[filename] = last_modification
            return False, []
        if last_modification <= self._files[filename]:
            self._d_cache_hits += 1
            return True, self._cached_data[filename]

        self._files[filename] = last_modification
        return False, []

    def ProduceTargets(self):
        """
        Gives off the completion candidates for this completer
        """

        if self.completion_wanted:
            return self._FindTarget()
        else:
            return []

    def _FindTarget(self):
        pass

class LatexSlave (GenericSlave):

    def __init__(self, arguments):
        super( LatexSlave , self).__init__(arguments['output'])
        self.collect_regex = arguments['collect']
        self.extensions = ".latexmain"
        self._completion_target = arguments['target']

    def BuildOurCompletes(self, name):
        """
        Surround the response value with brackets.
        TODO- perhaps add a square bracket option
        """
        return responses.BuildCompletionData("{" + name + "}",
                self._completion_target, None, name)


    def _FindTarget(self):
        """
        Find LaTeX labels for various completions

        This time we scan through all .tex files in the current
        directory and extract the content of all relevant commands
        as sources for completion.
        """
        ret = []
        for filename in self._Walk(self._main_directory, ".tex"):
            skip, cache = self._CacheDataAndSkip(filename)
            if skip:
                ret.extend(cache)
                continue

            resp = []
            for i, line in enumerate(codecs.open(filename, 'r', 'utf-8')):
                line = line.rstrip()
                match = re.search(self.collect_regex, line)
                if match is not None:
                    lid = re.sub(".*" + self.collect_regex + ".*", r"\1", line)
                    if not lid in ret and not lid in resp:
                        resp.append( lid )
                    #TODO- make it an option if we want gotos for
                    #this completion
                    self._goto_labels[lid] = (filename, i+1, match.start(1))

            self._cached_data[filename] = resp
            ret.extend(resp)
        """
        we moved the building of completes to here so we can
        share a cache between square and curly brackets
        """
        temp = []
        for i in ret:
            tempo = self.BuildOurCompletes(i)
            temp.append( tempo ) 
        return temp

class BibTexSlave (GenericSlave):
    def __init__(self):
        super( BibTexSlave , self).__init__(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?")
        self.extensions = ".bib"
        self._completion_target = 'Bib'

    def _FindBibEntriesRegex(self):
        """
        """
        ret = []
        for filename in self._Walk(self._main_directory, ".bib"):
            skip, cache = self._CacheDataAndSkip(filename)
            if skip:
                ret.extend(cache)
                continue

            resp = []
            for line in codecs.open(filename, 'r', 'utf-8'):
                line = line.rstrip()
                found = re.search(r"@(.*){([^,]*).*", line)
                if found is not None:
                    if found.group(1) != "string":
                        resp.append(responses.BuildCompletionData(
                            re.sub(r"@(.*){([^,]*).*", r"\2", line))
                        )

            ret.extend(resp)
            self._cached_data[filename] = resp
        return ret

    def _FindBibEntriesParser(self):
        """
        """
        ret = []
        parser = BibTexParser()
        parser.customization = bib_customizations
        for filename in self._Walk(self._main_directory, ".bib"):
            skip, cache = self._CacheDataAndSkip(filename)
            if skip:
                ret.extend(cache)
                continue

            resp = []
            with open(filename) as bibtex_file:
                bib_database = bibtexparser.load(bibtex_file, parser=parser)
                for entry in bib_database.entries:
                    if 'ID' not in entry:
                        continue
                    title = entry['title']
                    author = entry['author']
                    resp.append(responses.BuildCompletionData(
                        entry['ID'],
                        "%s (%s)" % (title, author)
                    ))

            ret.extend(resp)
            self._cached_data[filename] = resp
        return ret

    def _FindTarget(self):
        """
        Find BIBtex entries.

        Using a proper BibTeXParser to be able to retrieve field from the bib
        entry and add it as a help into YCM popup.

        If the BibTexParser module is not available, fallbacks to smart regexes
        to only acquire bibid
        """
        if nobibparser:
            return self._FindBibEntriesRegex()
        else:
            return self._FindBibEntriesParser()

class LatexCompleter( Completer ):
    """
    Completer for LaTeX that takes into account BibTex entries
    for completion.
    """

    def __init__( self, user_options ):
        super( LatexCompleter, self ).__init__( user_options )
        self.environment_completer   = LatexSlave({'output' : r"\\(begin|end)",
            'collect': r"\\begin\{(.*?)\}",
            'target': "Env"})
        self.ref_completer           = LatexSlave({'output':r"\\[a-zA-Z]*ref",
            'collect': r"\\\w*(?<!contents)label\{(.*?)\}",
            'target': "Ref"})
        self.bib_completer           = BibTexSlave()
        self.completers              = [self.environment_completer, self.ref_completer,
                self.bib_completer]
        #self.logfile            = open("/home/veesh/latexlog", "w")
        

    def ShouldUseNowInner( self, request_data ):

        cursor      = request_data["column_codepoint"] - 1 
        match_start = request_data["start_codepoint"]  - 1
        line        = request_data["line_value"]


        should_use = False
        line_splitted = line[ : match_start ]
        line_left     = line[ match_start : cursor ]

        if match_start:
            if  line[match_start] == '\\':
                return should_use

        """
        self.logfile.write("line split: " + line_splitted + "\n")
        self.logfile.write("line  left: " + line_left + "\n")
        self.logfile.write("full  line: " + line + "\n")
        self.logfile.write("\n")
        """
        
        for x in self.completers:
            if not should_use:
                should_use = x.ShouldUse(line_splitted, request_data)
            else:
               x.ShouldUse(line_splitted, request_data)


        #self.logfile.flush()
        return should_use


    def SupportedFiletypes( self ):
        """
        Determines which vim filetypes we support
        """
        return ['plaintex', 'tex']

    def _GoToDefinition(self, request_data):
        def find_end_of_command(line, match):
            if match is None:
                return -1
            for i in range(match.start(), len(line)):
                e = line[i]
                if e == "}":
                    return i
            return -1

        line = utils.ToUnicode(request_data["line_value"])
        match = self._ref_reg.search(line)
        end_of_command = find_end_of_command(line, match)
        if end_of_command == -1:
            raise RuntimeError( 'Can\'t jump to definition or declaration: not implemented yet' )
        else:
            ref = line[match.end():end_of_command]
            if ref not in self._goto_labels:
                raise RuntimeError( 'Can\'t jump to definition or declaration: not implemented yet' )
            filename, line, col = self._goto_labels[ref]
            return responses.BuildGoToResponse( filename, line, col )

    def GetSubcommandsMap( self ):
        return {
        'GoToDefinition'           : ( lambda self, request_data, args:
            self._GoToDefinition( request_data ) ),
        'GoToDeclaration'          : ( lambda self, request_data, args:
            self._GoToDefinition( request_data ) ),
        'GoTo'                     : ( lambda self, request_data, args:
            self._GoToDefinition( request_data ) ),
        }

    def GetDetailedDiagnostic( self, request_data ):
        return responses.BuildDisplayMessageResponse(
      self.DebugInfo(request_data))

    def DebugInfo( self, request_data ):
        """
        bib_dir = "Looking for *.bib in %s" % self._main_directory
        cache   = "Number of cached files: %i" % len(self._files)
        hits    = "Number of cache hits: %i" % self._d_cache_hits
        return "%s\n%s\n%s" % (bib_dir, cache, hits)
        """
        pass

    def ComputeCandidatesInner( self, request_data ):
        """
        Worker function executed by the asynchronous
        completion thread.
        """
        candidates = []

        for i in self.completers:
            candidates.extend(i.ProduceTargets())

        print(request_data['query'], sys.stderr)

        return candidates
