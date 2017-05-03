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

* You need to add a semantic completion part in your .vimrc:
```bash
    let g:ycm_semantic_triggers = {
        \ 'tex'  : ['{']
    \}
```

## BibTeXParser

To enhance the popup completion with part of the title and authors, we use the bibtexparser
module from this [repository](https://github.com/sciunto-org/python-bibtexparser).

This allows YCM to display a popup like this :

```
turing:1935     On Computable Numbers... (Turing Alan)
knuth:1984      Literate Programming (Knuth Donald E.)
```

You can install the bibtexparser via easy_install or pip

```bash
sudo pip install bibtexparser
```

If the bibtexparser is not present on the system, the completer will fallback into
the bibid only mode displaying only bibids in the completion popup.

Are there limitations?
----------------------

Of course:

* Your .tex and .bib files should be in UTF-8.
* You absolutely need to have a .bib file, because that is how the completer is able
to determine the main directory of your .tex project.
