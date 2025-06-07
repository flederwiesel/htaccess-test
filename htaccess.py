#!/usr/bin/env python3

"""Check URIs for expected HTTP status code and headers to test whether
redirections on a HTTP server work properly"""

import json
import requests
import sys

RED = "\033[31m"
GRE = "\033[32m"
YEL = "\033[33m"
NON = "\033[0m"

class Testcase:
    def __init__(self, line: int, uri: str, flags = None):
        self._line = line
        self._uri = uri
        self._flags = flags
        self._responses = []

    @property
    def line(self) -> str:
        return self._line

    @property
    def uri(self) -> str:
        return self._uri

    @property
    def flags(self) -> str:
        return self._flags

    @property
    def responses(self): # -> list[dict]:
        return self._responses

    def addresp(self, line: int, status: int) -> None:
        self._responses += [{"line": line, "status": status}]

    def addheader(self, header: str, content: str) -> None:
        self._responses[-1][header] = content

    def __repr__(self):
        resp = json.dumps(self._responses, indent=4)
        flags = f" ({self._flags})" if self._flags else ""

        return f"\033[37;1m{self.uri}\033[m{flags} \033[36m{resp}\033[m"

class TestSuite:

    @classmethod
    def load(cls, filename: str): # -> list[dict]:
        """Get a list of test cases from file, each being a dict of
        line number, request and expected response"""

        tests = []
        lineno = 0

        with open(filename, "r", encoding="utf-8") as file:
            uri = None
            responses = []

            for line in file:
                lineno += 1
                line = line.strip()

                if line.startswith("#"):
                    continue

                if not line:
                    uri = None
                else:
                    if uri:
                        try:
                            # Content-Type: text/html; charset=UTF-8
                            header, content = line.split(": ")
                            test.addheader(header, content)
                        except ValueError:
                            # 301
                            test.addresp(lineno, int(line))
                    else:
                        try:
                            # http://localhost follow
                            uri, flags = line.split(" ")
                            test = Testcase(lineno, uri, flags)
                        except ValueError:
                            # http://localhost
                            uri = line
                            test = Testcase(lineno, uri)

                        tests += [test]

        return tests


if __name__ == "__main__":
    if len(sys.argv) > 1:
        tests = TestSuite.load(sys.argv[1])

        for test in tests:
            #print(test)
            uri = test.uri
            diff = []

            for expect in test.responses:
                #print(uri)
                resp = requests.get(uri, allow_redirects=False)

                line = expect["line"]
                status = expect["status"]

                if int(resp.status_code) != status:
                    diff += [(line, None, status, resp.status_code)]

                del expect["line"]
                del expect["status"]

                for header, content in expect.items():
                    if header not in resp.headers:
                        diff += [(line, header, content, None)]
                    else:
                        if resp.headers[header] != content:
                            diff += [(line, header, content, resp.headers[header])]

                if diff:
                    break
                else:
                    uri = resp.headers["location"] if "location" in resp.headers else None

            if diff:
                print(f"<@ {test.line}: {test.uri}")

                for line, name, expect, result in diff:
                    print(f">@ {line}:")

                    if name:
                        print(f"\t{GRE}-{name}: {expect}{NON}")

                        if result:
                            print(f"\t{RED}+{name}: {result}{NON}")
                    else:
                        print(f"\t{GRE}-{expect}{NON}")

                        if result:
                            print(f"\t{RED}+{result}{NON}")

                sys.exit(1)
