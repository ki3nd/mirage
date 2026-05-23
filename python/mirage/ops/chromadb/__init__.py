from mirage.ops.chromadb.grep import grep
from mirage.ops.chromadb.read import read
from mirage.ops.chromadb.readdir import readdir
from mirage.ops.chromadb.search import search
from mirage.ops.chromadb.stat import stat

OPS = [grep, read, readdir, stat, search]
