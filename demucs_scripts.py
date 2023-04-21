import io
import os
import pathlib
import select
import subprocess as sp
import sys
from pathlib import Path
from shutil import rmtree
from typing import IO, Dict, Optional, Tuple

model = "htdemucs"
extensions = ["mp3", "wav", "ogg", "flac", "webm"]  # we will look for all those file types.
two_stems = None   # only separate one stems from the rest, for instance
# two_stems = "vocals"

# Options for the output audio.
mp3 = True
mp3_rate = 320
float32 = False  # output as float 32 wavs, unsused if 'mp3' is True.
int24 = False    # output as int24 wavs, unused if 'mp3' is True.
# You cannot set both `float32 = True` and `int24 = True` !!

in_path = '/content/demucs/'
out_path = '/content/demucs_separated/'

def find_files(in_path):
    out = []
    for file in Path(in_path).iterdir():
        if file.suffix.lower().lstrip(".") in extensions:
            out.append(file)
    return out

def copy_process_streams(process: sp.Popen):
    def raw(stream: Optional[IO[bytes]]) -> IO[bytes]:
        assert stream is not None
        if isinstance(stream, io.BufferedIOBase):
            stream = stream.raw
        return stream

    p_stdout, p_stderr = raw(process.stdout), raw(process.stderr)
    stream_by_fd: Dict[int, Tuple[IO[bytes], io.StringIO, IO[str]]] = {
        p_stdout.fileno(): (p_stdout, sys.stdout),
        p_stderr.fileno(): (p_stderr, sys.stderr),
    }
    fds = list(stream_by_fd.keys())

    while fds:
        # `select` syscall will wait until one of the file descriptors has content.
        ready, _, _ = select.select(fds, [], [])
        for fd in ready:
            p_stream, std = stream_by_fd[fd]
            raw_buf = p_stream.read(2 ** 16)
            if not raw_buf:
                fds.remove(fd)
                continue
            buf = raw_buf.decode()
            std.write(buf)
            std.flush()

def separate(inp=None, outp=None):
    inp = inp or in_path
    outp = outp or out_path
    cmd = ["python3", "-m", "demucs.separate", "-o", str(outp), "-n", model, "-d" , "cuda",   "--overlap", "0.12", "-j", "8", "--segment", "10"]
    if mp3:
        cmd += ["--mp3", f"--mp3-bitrate={mp3_rate}"]
    if float32:
        cmd += ["--float32"]
    if int24:
        cmd += ["--int24"]
    if two_stems is not None:
        cmd += [f"--two-stems={two_stems}"]
    files = [inp]
    if not files:
        print(f"No valid audio files in {in_path}")
        return
    print("Going to separate the files:")
    print('\n'.join(files))
    print("With command: ", " ".join(cmd))
    print(f"output path: {outp}")
    
    inp_path = pathlib.PurePath(inp)
    file_name = inp_path.name
    file_name_dir = ".".join(file_name.split(".")[:-1])
    vocals_path = Path(outp) / model / file_name_dir / "vocals.mp3"
    print(f"vocals path: {vocals_path}")

    p = sp.Popen(cmd + files, stdout=sp.PIPE, stderr=sp.PIPE)
    #copy_process_streams(p)
    

    while p.poll() is None:
        if os.path.exists(vocals_path):
            print("vocals file found, terminating process")
            p.kill()
            break
    
    print("finished")
    
    return vocals_path