# Sites Configuration (sites.yml)

The `config/sites.yml` file defines the sites the crawler will index.

## Basic structure

```yaml
sites:
  - name: "Site name"
    crawl: "https://example.com"
    type: html          # html | json | mediawiki
    max_pages: 500      # 0 = unlimited
    depth: 3
```

## Source types

### `html` — Standard website

Follows links from the starting URL up to the specified depth.

```yaml
- name: "My site"
  crawl: "https://example.com"
  type: html
  max_pages: 1000
  depth: 4
  delay: 1.0                    # Delay between requests (seconds)
  selector: ".article-content"  # CSS selector for main content (optional)
  exclude:
    - "/login"
    - "/admin"
  no_index:                     # Visited for link discovery but not indexed
    - "/categories"
```

### `mediawiki` — Wikipedia, Vikidia...

Uses the MediaWiki API to efficiently fetch all pages.

```yaml
- name: "Vikidia FR"
  crawl: "https://fr.vikidia.org"
  type: mediawiki
  max_pages: 50000
```

### `json` — JSON API

```yaml
- name: "My API"
  crawl: "https://api.example.com/articles"
  type: json
  lang: "en"
  json:
    root: "items"                                        # Root key containing the list
    title: "title"
    url: "https://example.com/article/{{id}}"           # Template with variables
    content: "body,summary"                              # Content fields (comma-separated)
    image: "thumbnail_url"
```

## Full property reference

| Property | Type | Description |
|---|---|---|
| `name` | string | Site name (used for filtering in Typesense) |
| `crawl` | string | Starting URL |
| `type` | string | `html`, `json` or `mediawiki` |
| `max_pages` | int | Max pages to crawl (0 = unlimited) |
| `depth` | int | Max link-following depth (html only) |
| `delay` | float | Delay between requests in seconds |
| `selector` | string | CSS selector for content (html only) |
| `lang` | string | Content language: `fr`, `en`... |
| `exclude` | list | URL patterns to skip entirely |
| `no_index` | list | URL patterns visited but not indexed |
| `json` | object | JSON field mapping (json type only) |

## Full example

```yaml
sites:
  # French children's encyclopedia
  - name: "Vikidia"
    crawl: "https://fr.vikidia.org"
    type: mediawiki
    max_pages: 0

  # Educational news site
  - name: "1jour1actu"
    crawl: "https://www.1jour1actu.com"
    type: html
    max_pages: 2000
    depth: 3
    delay: 1.5
    selector: ".entry-content"
    exclude:
      - "/wp-admin"
      - "/feed"
      - ".pdf"

  # Educational resources API
  - name: "Resources EN"
    crawl: "https://api.educationresources.example.com/list"
    type: json
    lang: "en"
    json:
      root: "resources"
      title: "name"
      url: "https://educationresources.example.com/resource/{{id}}"
      content: "description,full_text"
      image: "cover_image"
```

## Available files

- `config/sites.yml` — active configuration (not versioned)
- `config/sites.yml.example` — example to copy from
- `config/sites-complet.yml` — extended list of educational sites
