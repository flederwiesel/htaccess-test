# Apache .htaccess files and result checking script

Check whether your `.htaccess` files work as expected by checking against a script
containing request URIs and expected status codes and headers for the response.

Redirections will be followed for as many times as responses are defined.

The first mismatch will abort the test.

## Command Line

Simply call

```
./htaccess-test.py <filename>
```

## File format

Records consisting of Request Methods/URIs, followed by one or a sequence of
expected responses, separated by empty lines.

Requests are denoted by `<` followed by an (optional) HTTP method and the URI.

Each item in to be checked in the response(s) is started by `>`. The first item
has to be the HTTP status code, each stats code denoting a new response.

Following the status you may specify a header as `Header-Name: value` or a text
fragent to be searched in the response data by prefixing the text with `=`.
Multiple text fragments in the response will be searched separately, the order
of which will not be checked in the response.

Which means, checking a valid HTML document, this will match both lines,
therefore passing the test:

```
< GET https://localhost
    > =</html>
    > =<html>
```

`#` is used as comment char, if it is the first non-whitespace char on the line.

Lines may be indendet but don't have to.

Example:

```sh
# URI to be requested, including query string
< HEAD http://example.net
    # Expected HTTP status code of first response
    > 301
    # Response header to be checked for first response
    > Location: https://example.net/
    # Response of follow-up request
    > 302
    > Location: https://example.net/
    # Houston, we have a problem...
    > 302
    > Location: https://example.net/
    > 302
    > 302
    > 302
    # Only status is OK
    > 302
    # Add more lines if you still want to follow...

# Next check:
< HEAD https://example.net/file-not-found
    > 404
    # Site is expected to send a picture on 404 responses
    > Content-Type: image/png
    > Content-Length: 666
```
