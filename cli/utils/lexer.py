from prompt_toolkit.lexers import Lexer
from prompt_toolkit.document import Document

class RunLexer(Lexer):
    def lex_document(self, document: Document):
        def get_line(lineno):
            line = document.lines[lineno]

            lower = line.lower()

            if lower == "run":
                return [("class:command", line)]

            if lower == "exit":
                return [("class:command", line)]
            
            if lower.startswith("run "):
                return [
                    ("class:command", line[:3]),
                    ("", line[3:])
                ]
            
            if lower == "gh auth" or lower == "gh":
                return [("class:command", line)]

            return [("", line)]

        return get_line
