vim-ycm-latex-semantic-completer
===========

What is this?
-------------

This is a Latex Completer for [YouCompleteMe](https://github.com/Valloric/YouCompleteMe).
It completes citations (`\cite{}`) and references to labels (`\ref{}`). It is based
on an old version of [vim-ycm-tex](https://github.com/bjoernd/vim-ycm-tex) 
that was using Linux commands to extract labels and bibliography IDs.

How do I use it?
----------------

* YCM completers need to be made available in your YCM directory. There's a
  subdirectory `$HOME/.vim/bundle/YouCompleteMe/third_party/ycmd/ycmd/completers/tex`.  
  This completer should be added in the tex directory (create it if it does not exist)
  
* The completer will look for a .bib file to determine the main directory of your
project. When this is done, it is able to walk through every subdirectory to index
labels and bib ids.

Are there limitations?
----------------------

Of course:

* Your .tex and .bib files should be in UTF-8.
* You absolutely need to have a .bib file, because that is how the completer is able
to determine the main directory of your .tex project.
