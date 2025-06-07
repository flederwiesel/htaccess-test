# Apache .htaccess files and result checking script

Check whether your redirections work as expected by comparing to a file
containing expected status codes and headers for URIs.

Redirections will be followed for as many times as responses are defined.

The first mismatch will abort the test.

## Command Line

Simply call

```
./htaccess.py <filename>
```

## File format

Records consisting of Request URIs, followed by one or a sequence of expected
responses, separated by empty lines.

Each response is started by HTTP status and may be followed by HTTP headers.

`#` is used as comment char, if it is the first non-whitespace char on the line.

Lines may be indendet but don't have to.

Example:

```sh
# URI to be requested, including query string
http://example.net
    # Expected HTTP status code of first response
    301
    # Response header to be checked for first response
    Location: https://example.net/
    # Response of follow-up request
    302
    Location: https://example.net/
    # Houston, we have a problem...
    302
    Location: https://example.net/
    302
    302
    302
    # Only status is OK
    302
    # Add more lines if you still want to follow...

# Next check:
https://example.net/file-not-found
    404
    # Site is expected to send a picture on 404 responses
    Content-Type: image/png
    Content-Length: 666
```
