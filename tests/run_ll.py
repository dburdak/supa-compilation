import sys, os, ctypes, tempfile
import llvmlite.binding as llvm

llvm.initialize_native_target()
llvm.initialize_native_asmprinter()

def run_ll_file(path):
    with open(path) as f:
        ir_text = f.read()

    mod = llvm.parse_assembly(ir_text)
    mod.verify()

    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine()
    engine = llvm.create_mcjit_compiler(mod, target_machine)
    engine.finalize_object()
    engine.run_static_constructors()

    main_ptr = engine.get_function_address("main")
    cfunc = ctypes.CFUNCTYPE(ctypes.c_int32)(main_ptr)

    # capture C-level stdout (printf writes through libc, so redirect fd 1)
    stdout_fd = sys.stdout.fileno()
    saved_fd = os.dup(stdout_fd)
    tmp = tempfile.TemporaryFile(mode="w+")
    os.dup2(tmp.fileno(), stdout_fd)
    try:
        ret = cfunc()
    finally:
        libc = ctypes.CDLL(None)
        libc.fflush(None)
        os.dup2(saved_fd, stdout_fd)
        os.close(saved_fd)

    tmp.seek(0)
    captured = tmp.read()
    tmp.close()
    return ret, captured


if __name__ == "__main__":
    ret, out = run_ll_file(sys.argv[1])
    sys.stdout.write(out)
    sys.exit(ret)
