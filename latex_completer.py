#!/usr/bin/env python

import re
import logging
import sys
import os
import codecs

from ycmd.completers.completer import Completer
from ycmd import responses
from ycmd import utils

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
        line = utils.ToUtf8IfNeeded(request_data["line_value"])

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

    def _FindBibEntries(self):
        """
        Find BIBtex entries.

        I'm currently assuming, that Bib entries have the format
        ^@<articletype> {<ID>,
            <bibtex properties>
            [..]
        }

        Hence, to find IDs for completion, I scan for lines starting
        with an @ character and extract the ID from there.
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
