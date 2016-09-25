#!/usr/bin/env python

import re
import logging
import sys
import os
import codecs

from ycmd.completers.completer import Completer
from ycmd import responses
from ycmd import utils


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

class LatexCompleter( Completer ):
    """
    Completer for LaTeX that takes into account BibTex entries
    for completion.
    """

    def __init__( self, user_options ):
        super( LatexCompleter, self ).__init__( user_options )
        self._completion_target = 'none'
        self._main_directory    = None
        self._cite_reg          = re.compile("cite.*\{")
        self._ref_reg           = re.compile("ref\{|pageref\{")

    def ShouldUseNowInner( self, request_data ):
        #q    = utils.ToUtf8IfNeeded(request_data['query'])
        #col  = request_data["start_column"]
        line = utils.ToUnicode(request_data["line_value"])

        if self._main_directory is None:
            self._ComputeMainDirectory(request_data)

        should_use = False
        line_splitted = line
        match = self._cite_reg.search(line_splitted)
        if match is not None:
            self._completion_target = 'cite'
            should_use = True

        match = self._ref_reg.search(line_splitted)
        if match is not None:
            if self._completion_target == 'cite':
                self._completion_target = 'all'
            else:
                self._completion_target = 'label'
            should_use = True

        return should_use


    def SupportedFiletypes( self ):
        """
        Determines which vim filetypes we support
        """
        return ['plaintex', 'tex']

    def _Walk( self, path, what ):
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(what):
                    yield os.path.join(root, file)

    def _ComputeMainDirectory( self, request_data ):
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

        if not FindMain(path, ".bib"):
            self._main_directory = filepath
            print >> sys.stderr, "Unable to set the main directory..."
        else:
            print >> sys.stderr, "Main directory successfully found at %s" % self._main_directory

    def _FindBibEntriesRegex(self):
        """
        """
        ret = []
        for filename in self._Walk(self._main_directory, ".bib"):
            for line in codecs.open(filename, 'r', 'utf-8'):
                line = line.rstrip()
                found = re.search(r"@(.*){([^,]*).*", line)
                if found is not None:
                    if found.group(1) != "string":
                        ret.append(responses.BuildCompletionData(
                            re.sub(r"@(.*){([^,]*).*", r"\2", line))
                        )
        return ret

    def _FindBibEntriesParser(self):
        """
        """
        ret = []
        parser = BibTexParser()
        parser.customization = bib_customizations
        for filename in self._Walk(self._main_directory, ".bib"):
            with open(filename) as bibtex_file:
                bib_database = bibtexparser.load(bibtex_file, parser=parser)
                for entry in bib_database.entries:
                    if 'ID' not in entry:
                        continue
                    title = entry['title']
                    author = entry['author']
                    ret.append(responses.BuildCompletionData(
                        entry['ID'],
                        "%s (%s)" % (title, author)
                    ))
        return ret

    def _FindBibEntries(self):
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


    def _FindLabels(self):
        """
        Find LaTeX labels for \ref{} completion.

        This time we scan through all .tex files in the current
        directory and extract the content of all \label{} commands
        as sources for completion.
        """
        ret = []
        for filename in self._Walk(self._main_directory, ".tex"):
            for line in codecs.open(filename, 'r', 'utf-8'):
                line = line.rstrip()
                if re.search(r".*\label{(.*)}.*", line) is not None:
                    ret.append(responses.BuildCompletionData(
                        re.sub(r".*\label{(.*)}.*", r"\1", line))
                        )
        return ret
    
    def _GoToDefinition(self, request_data):
        raise RuntimeError( 'Can\'t jump to definition or declaration: not implemented yet' )

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
        return "Looking for *.bib in %s" % self._main_directory

    def ComputeCandidatesInner( self, request_data ):
        """
        Worker function executed by the asynchronous
        completion thread.
        """
        candidates = []

        if self._main_directory is None:
            self._ComputeMainDirectory(request_data)

        if self._completion_target == 'cite':
            candidates = self._FindBibEntries()
        elif self._completion_target == 'label':
            candidates = self._FindLabels()
        elif self._completion_target == 'all':
            candidates = self._FindLabels() + self._FindBibEntries()

        print >> sys.stderr, request_data['query']

        return candidates
