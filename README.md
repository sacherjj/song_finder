# song_finder

This project is to allow a user to search for songs similar to a start song and artist.  Along the search,
if a user accepts a song, it downloads an mp3 format of that some from YouTube and adds similar songs to the accepted
one to the end of the approval queue.

The interface can be command line or GUI using tkinter.  I have also setup to build using PyInstaller for Windows.
Due to the youtube-dl requirement, I cannot build without the command line for PyInstaller.

## Origin

Started as a modification of [a command line program.](https://github.com/schollz/playlistfromsong).  However, I wound up
with an almost complete rewrite that was no longer in any way compatible.  Since the original project name also was
no longer compatible, I decided to start a new repository.  This program is more of an interactive search, rather than this
project's batch mode.

