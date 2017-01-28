#!/usr/bin/python

# INFORMATION:
# This scripts compiles the original Unicorn framework to JavaScript

import os
import shutil
import stat

EXPORTED_FUNCTIONS = [
    '_uc_version',
    '_uc_arch_supported',
    '_uc_open',
    '_uc_close',
    '_uc_query',
    '_uc_errno',
    '_uc_strerror',
    '_uc_reg_write',
    '_uc_reg_read',
    '_uc_reg_write_batch',
    '_uc_reg_read_batch',
    '_uc_mem_write',
    '_uc_mem_read',
    '_uc_emu_start',
    '_uc_emu_stop',
    '_uc_hook_add',
    '_uc_hook_del',
    '_uc_mem_map',
    '_uc_mem_map_ptr',
    '_uc_mem_unmap',
    '_uc_mem_protect',
    '_uc_mem_regions',
]

# Directories
UNICORN_DIR = os.path.abspath("unicorn")
UNICORN_QEMU_DIR = os.path.join(UNICORN_DIR, "qemu")
ORIGINAL_QEMU_DIR = os.path.abspath("externals/qemu-2.2.1")

#############
# Utilities #
#############

# Replace strings in files
def replace(path, replacements):
    pathBak = path + ".bak"
    if os.path.exists(pathBak):
        return
    shutil.move(path, pathBak)
    fin = open(pathBak, "rt")
    fout = open(path, "wt")
    for line in fin:
        for string in replacements:
            line = line.replace(string, replacements[string])
        fout.write(line)
    fin.close()
    fout.close()

# Insert strings in files after a specific line
def insert(path, match, strings):
    pathBak = path + ".bak"
    if os.path.exists(pathBak):
        return
    shutil.move(path, pathBak)
    fin = open(pathBak, "rt")
    fout = open(path, "wt")
    for line in fin:
        fout.write(line)
        if match.strip() == line.strip():
            for string in strings:
                fout.write(string + "\n")
    fin.close()
    fout.close()

# Copy directory contents to another folder without overwriting files
def copytree(src, dst, symlinks=False, ignore=None):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copytree(s, d, symlinks, ignore)
        elif not os.path.exists(d):
            shutil.copy2(s, d)


############
# Patching #
############

REPLACE_OBJECTS = """
import re, glob, shutil
path = 'qemu/*softmmu/**/*.o'
for d in xrange(5):
    for f in glob.glob(path.replace('/**', '/*' * d)):
        f = f.replace('\\\\', '/')
        m = re.match(r'qemu\/([0-9A-Za-z_]+)\-softmmu.*', f)
        shutil.move(f, f[:-2] + '-' + m.group(1) + '.o')
"""

def patchUnicornTCI():
    """
    Patches Unicorn's QEMU fork to add the TCG Interpreter backend
    """
    # Enable TCI
    replace(os.path.join(UNICORN_QEMU_DIR, "configure"), {
        "tcg_interpreter=\"no\"": "tcg_interpreter=\"yes\""
    })
    # Add executable permissions for the new configure file
    path = os.path.join(UNICORN_QEMU_DIR, "configure")
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC)
    # Copy missing TCI source files and patch them with Unicorn updates
    copytree(ORIGINAL_QEMU_DIR, UNICORN_QEMU_DIR)
    replace(os.path.join(UNICORN_QEMU_DIR, "tcg/tci/tcg-target.c"), {
        "tcg_target_available_regs": "s->tcg_target_available_regs",
        "tcg_target_call_clobber_regs": "s->tcg_target_call_clobber_regs",
        "tcg_add_target_add_op_defs(": "tcg_add_target_add_op_defs(s, ",
    })
    replace(os.path.join(UNICORN_QEMU_DIR, "tcg/tci/tcg-target.h"), {
        "#define tcg_qemu_tb_exec": "//#define tcg_qemu_tb_exec",
    })
    # Add TCI to Makefile.targets
    insert(os.path.join(UNICORN_QEMU_DIR, "Makefile.target"),
        "obj-y += tcg/tcg.o tcg/optimize.o", [
            "obj-$(CONFIG_TCG_INTERPRETER) += tci.o"
        ]
    )
    # Add TCI symbols
    insert(os.path.join(UNICORN_QEMU_DIR, "header_gen.py"),
        "symbols = (", [
            "    'tci_tb_ptr',",
            "    'tcg_qemu_tb_exec',",
        ]
    )
    # Update platform headers with new symbols
    cmd = "bash -c \"cd " + UNICORN_QEMU_DIR + " && ./gen_all_header.sh\""
    os.system(cmd)


def patchUnicornJS():
    """
    Patches Unicorn files to target JavaScript
    """
    # Disable unnecessary options
    replace(os.path.join(UNICORN_DIR, "config.mk"), {
        "UNICORN_DEBUG ?= yes": "UNICORN_DEBUG ?= yes", # TODO: Change to `no`
        "UNICORN_SHARED ?= yes": "UNICORN_SHARED ?= no",
        "UNICORN_ARCHS ?= x86 m68k arm aarch64 mips sparc": "UNICORN_ARCHS ?= x86 arm", # TODO: Remove line
    })
    # Ensure QEMU's object files have different base names
    name = "rename_objects.py"
    with open(os.path.join(UNICORN_DIR, name), "wt") as f:
        f.write(REPLACE_OBJECTS)
    replace(os.path.join(UNICORN_DIR, "Makefile"), {
        "$(MAKE) -C qemu -j 4":
        "$(MAKE) -C qemu -j 4\r\n\t@python " + name,
    })
    # Replace sigsetjmp/siglongjump with setjmp/longjmp
    replace(os.path.join(UNICORN_QEMU_DIR, "cpu-exec.c"), {
        "sigsetjmp(cpu->jmp_env, 0)": "setjmp(cpu->jmp_env)",
        "siglongjmp(cpu->jmp_env, 1)": "longjmp(cpu->jmp_env, 1)",
    })
    # Fix Glib function pointer issues
    replace(os.path.join(UNICORN_QEMU_DIR, "glib_compat.c"), {
        "(GCompareDataFunc) compare_func) (l1->data, l2->data, user_data)":
            "(GCompareFunc) compare_func) (l1->data, l2->data)",
    })
    # Fix unaligned reads
    replace(os.path.join(UNICORN_QEMU_DIR, "tci.c"), {
        "static uint32_t tci_read_i32(uint8_t **tb_ptr)":
        """
        static uint32_t tci_read_i32(uint8_t **tb_ptr) {
            uint32_t value =
                *((*tb_ptr)+0) <<  0 |
                *((*tb_ptr)+1) <<  8 |
                *((*tb_ptr)+2) << 16 |
                *((*tb_ptr)+3) << 24;
            *tb_ptr += sizeof(value);
            return value;
        }
        static uint32_t tci_read_i32_old(uint8_t **tb_ptr)
        """,
        
        "static int32_t tci_read_s32(uint8_t **tb_ptr)":
        """
        static int32_t tci_read_s32(uint8_t **tb_ptr) {
            int32_t value =
                *((*tb_ptr)+0) <<  0 |
                *((*tb_ptr)+1) <<  8 |
                *((*tb_ptr)+2) << 16 |
                *((*tb_ptr)+3) << 24;
            *tb_ptr += sizeof(value);
            return value;
        }
        static int32_t tci_read_s32_old(uint8_t **tb_ptr)
        """,
    })


############
# Building #
############

def compileUnicorn():
    # Patching Unicorn's QEMU fork
    patchUnicornTCI()
    patchUnicornJS()

    # Emscripten: Make
    os.chdir('unicorn')
    if os.name == 'posix':
        cmd = 'emmake make'
        os.system(cmd)
    os.chdir('..')

    # TODO: Use --cpu=unknown flag for QEMU's configure, can be passed via: `UNICORN_QEMU_FLAGS="--cpu=unknown" ./make.sh`.
    return

    # Compile static library to JavaScript
    cmd = os.path.expandvars('$EMSCRIPTEN/emcc')
    cmd += ' -Os --memory-init-file 0'
    cmd += ' unicorn/libunicorn.a'
    cmd += ' -s EXPORTED_FUNCTIONS=\"[\''+ '\', \''.join(EXPORTED_FUNCTIONS) +'\']\"'
    cmd += ' -s USE_PTHREADS=1'
    cmd += ' -s ALLOW_MEMORY_GROWTH=1'
    cmd += ' -o src/unicorn.out.js'
    os.system(cmd)


if __name__ == "__main__":
    # Initialize Unicorn submodule if necessary
    if not os.listdir(UNICORN_DIR):
        os.system("git submodule update --init")
    # Compile Unicorn
    if os.name in ['posix']:
        compileUnicorn()
    else:
        print "Your operating system is not supported by this script:"
        print "Please, use Emscripten to compile Unicorn manually to src/unicorn.out.js"
