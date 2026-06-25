# config.Repository

# config.Repository

Model representing a project repository in the Bakery configuration.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/repository.py#L32-L141)

``` python
config.Repository()
```

## Attributes

| Name                  | Description                                |
|-----------------------|--------------------------------------------|
| [revision](#revision) | Get the git commit SHA for the repository. |

### revision

Get the git commit SHA for the repository.

`revision``:`` ``str | None`

## Methods

| Name | Description |
|----|----|
| [deduplicate_authors()](#deduplicate_authors) | De-duplicate and sort authors. Logs a warning if duplicates are found. |
| [default_https_url_scheme()](#default_https_url_scheme) | Prepend ‘https://’ to the URL if it does not already start with it. |
| [parse_authors()](#parse_authors) | Parse the authors field into a list of NameEmail objects from dicts or as strings for later validation. |
| [parse_maintainer()](#parse_maintainer) | Parse the maintainer field into a NameEmail object or return as is if already a str for later validation. |

### deduplicate_authors()

De-duplicate and sort authors. Logs a warning if duplicates are found.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/repository.py#L119-L141)

``` python
deduplicate_authors(authors)
```

#### Parameters

`authors``:`` ``list[NameEmail]`  
The list of authors to deduplicate.

#### Returns

` ``list[NameEmail]`  
A list of unique authors.

### default_https_url_scheme()

Prepend ‘https://’ to the URL if it does not already start with it.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/repository.py#L68-L78)

``` python
default_https_url_scheme(value)
```

#### Parameters

`value``:`` ``Any`  
The URL to validate and possibly modify.

### parse_authors()

Parse the authors field into a list of NameEmail objects from dicts or as strings for later validation.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/repository.py#L80-L99)

``` python
parse_authors(value)
```

#### Parameters

`value``:`` ``list[Any]`  
The list of authors to parse.

#### Returns

` ``list[HashableNameEmail | str]`  
A list of HashableNameEmail objects parsed from dictionaries and/or strings.

### parse_maintainer()

Parse the maintainer field into a NameEmail object or return as is if already a str for later validation.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/repository.py#L101-L117)

``` python
parse_maintainer(value)
```

#### Parameters

`value``:`` ``Any`  
The maintainer to parse.

#### Returns

` ``HashableNameEmail | str`  
A HashableNameEmail object parsed from a dictionary or the string value if already a string.

Back to top
