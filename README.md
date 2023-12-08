# Auxillary Web Scraper For The Database Application For Tunes

This script was written in order to populate an instance of the database used in
[The Database Application For Tunes](https://github.com/me11203sci/Database-Application-For-Tunes/). It farmes the Spotify A.P.I. for metadata content
and uses the Invidious A.P.I. to provide the audio source(s) for hashing. In order
to speed up the parsing of metadata into the appropriate form, multiprocessing routines
are employed.

## Installating Dependencies

While there are many ways to skin the cat per say, we reccomend using
the [Mamba]() project for quick and frictionless experience. After installing [minimamba]()
use the included `enviroment.yaml` file to create the python enviroment using the following
command:

```
mamba env create --file enviroment.yaml 
```

Assuming there are no errors, then run:

```
mamba activate daft_scraper
```

And you should be good to go!

## Usage

TODO
