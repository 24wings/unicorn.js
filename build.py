#!/usr/bin/python

# INFORMATION:
# This scripts compiles the original Unicorn framework to JavaScript

import os
import shutil
import stat
import sys

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
    '_uc_context_alloc',
    '_uc_free',
    '_uc_context_save',
    '_uc_context_restore',
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
        "UNICORN_DEBUG ?= yes": "UNICORN_DEBUG ?= no",
        "UNICORN_SHARED ?= yes": "UNICORN_SHARED ?= no",
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
    # Fix QEMU function pointer issues
    replace(os.path.join(UNICORN_QEMU_DIR, "include/exec/helper-gen.h"), {
        "#include <exec/helper-head.h>": """#include <exec/helper-head.h>
        // Helper adapters
        #define CAT(a, ...) PRIMITIVE_CAT(a, __VA_ARGS__)
        #define PRIMITIVE_CAT(a, ...) a ## __VA_ARGS__

        #define IIF(c) PRIMITIVE_CAT(IIF_, c)
        #define IIF_0(t, ...) __VA_ARGS__
        #define IIF_1(t, ...) t

        #define PROBE(x) x, 1
        #define CHECK(...) CHECK_N(__VA_ARGS__, 0)
        #define CHECK_N(x, n, ...) n

        #define VOID_TYPE_void ()
        #define VOID_TYPE_noreturn ()
        #define VOID_PROBE(type)            VOID_PROBE_PROXY(VOID_TYPE_##type)
        #define VOID_PROBE_PROXY(...)       VOID_PROBE_PRIMITIVE(__VA_ARGS__)
        #define VOID_PROBE_PRIMITIVE(x)     VOID_PROBE_COMBINE_ x
        #define VOID_PROBE_COMBINE_(...)    PROBE(~)

        #define IS_VOID(type) CHECK(VOID_PROBE(type))


        #define GEN_ADAPTER_0_VOID(name) \
            HELPER(name)(); return 0;
        #define GEN_ADAPTER_0_NONVOID(name) \
            return HELPER(name)();
        #define GEN_ADAPTER_0(name, ret) \
        static uint32_t glue(adapter_helper_, name)( \
          uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4, uint32_t a5, \
          uint32_t a6, uint32_t a7, uint32_t a8, uint32_t a9, uint32_t a10) { \
            IIF(IS_VOID(ret)) (GEN_ADAPTER_0_VOID(name), GEN_ADAPTER_0_NONVOID(name)) \
        }

        #define GEN_ADAPTER_1_VOID(name, t1) \
            HELPER(name)((dh_ctype(t1))a1); return 0;
        #define GEN_ADAPTER_1_NONVOID(name, t1) \
            return HELPER(name)((dh_ctype(t1))a1);
        #define GEN_ADAPTER_1(name, ret, t1) \
        static uint32_t glue(adapter_helper_, name)( \
          uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4, uint32_t a5, \
          uint32_t a6, uint32_t a7, uint32_t a8, uint32_t a9, uint32_t a10) { \
            IIF(IS_VOID(ret)) (GEN_ADAPTER_1_VOID(name, t1), GEN_ADAPTER_1_NONVOID(name, t1)) \
        }

        #define GEN_ADAPTER_2_VOID(name, t1, t2) \
            HELPER(name)((dh_ctype(t1))a1, (dh_ctype(t2))a2); return 0;
        #define GEN_ADAPTER_2_NONVOID(name, t1, t2) \
            return HELPER(name)((dh_ctype(t1))a1, (dh_ctype(t2))a2);
        #define GEN_ADAPTER_2(name, ret, t1, t2) \
        static uint32_t glue(adapter_helper_, name)( \
          uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4, uint32_t a5, \
          uint32_t a6, uint32_t a7, uint32_t a8, uint32_t a9, uint32_t a10) { \
            IIF(IS_VOID(ret)) (GEN_ADAPTER_2_VOID(name, t1, t2), GEN_ADAPTER_2_NONVOID(name, t1, t2)) \
        }

        #define GEN_ADAPTER_3_VOID(name, t1, t2, t3) \
            HELPER(name)((dh_ctype(t1))a1, (dh_ctype(t2))a2, (dh_ctype(t3))a3); return 0;
        #define GEN_ADAPTER_3_NONVOID(name, t1, t2, t3) \
            return HELPER(name)((dh_ctype(t1))a1, (dh_ctype(t2))a2, (dh_ctype(t3))a3);
        #define GEN_ADAPTER_3(name, ret, t1, t2, t3) \
        static uint32_t glue(adapter_helper_, name)( \
          uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4, uint32_t a5, \
          uint32_t a6, uint32_t a7, uint32_t a8, uint32_t a9, uint32_t a10) { \
            IIF(IS_VOID(ret)) (GEN_ADAPTER_3_VOID(name, t1, t2, t3), GEN_ADAPTER_3_NONVOID(name, t1, t2, t3)) \
        }

        #define GEN_ADAPTER_4_VOID(name, t1, t2, t3, t4) \
            HELPER(name)((dh_ctype(t1))a1, (dh_ctype(t2))a2, (dh_ctype(t3))a3, (dh_ctype(t4))a4); return 0;
        #define GEN_ADAPTER_4_NONVOID(name, t1, t2, t3, t4) \
            return HELPER(name)((dh_ctype(t1))a1, (dh_ctype(t2))a2, (dh_ctype(t3))a3, (dh_ctype(t4))a4);
        #define GEN_ADAPTER_4(name, ret, t1, t2, t3, t4) \
        static uint32_t glue(adapter_helper_, name)( \
          uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4, uint32_t a5, \
          uint32_t a6, uint32_t a7, uint32_t a8, uint32_t a9, uint32_t a10) { \
            IIF(IS_VOID(ret)) (GEN_ADAPTER_4_VOID(name, t1, t2, t3, t4), GEN_ADAPTER_4_NONVOID(name, t1, t2, t3, t4)) \
        }

        #define GEN_ADAPTER_5_VOID(name, t1, t2, t3, t4, t5) \
            HELPER(name)((dh_ctype(t1))a1, (dh_ctype(t2))a2, (dh_ctype(t3))a3, (dh_ctype(t4))a4, (dh_ctype(t5))a5); return 0;
        #define GEN_ADAPTER_5_NONVOID(name, t1, t2, t3, t4, t5) \
            return HELPER(name)((dh_ctype(t1))a1, (dh_ctype(t2))a2, (dh_ctype(t3))a3, (dh_ctype(t4))a4, (dh_ctype(t5))a5);
        #define GEN_ADAPTER_5(name, ret, t1, t2, t3, t4, t5) \
        static uint32_t glue(adapter_helper_, name)( \
          uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4, uint32_t a5, \
          uint32_t a6, uint32_t a7, uint32_t a8, uint32_t a9, uint32_t a10) { \
            IIF(IS_VOID(ret)) (GEN_ADAPTER_5_VOID(name, t1, t2, t3, t4, t5), GEN_ADAPTER_5_NONVOID(name, t1, t2, t3, t4, t5)) \
        }
        """,

        "tcg_gen_callN(tcg_ctx, HELPER(name)":
        "tcg_gen_callN(tcg_ctx, glue(adapter_helper_, name)",

        "#define DEF_HELPER_FLAGS_0(name, flags, ret)                            \\":"""
         #define DEF_HELPER_FLAGS_0(name, flags, ret)                            \\
         GEN_ADAPTER_0(name, ret) \\""",
        "#define DEF_HELPER_FLAGS_1(name, flags, ret, t1)                        \\":"""
         #define DEF_HELPER_FLAGS_1(name, flags, ret, t1)                        \\
         GEN_ADAPTER_1(name, ret, t1) \\""",
        "#define DEF_HELPER_FLAGS_2(name, flags, ret, t1, t2)                    \\":"""
         #define DEF_HELPER_FLAGS_2(name, flags, ret, t1, t2)                    \\
         GEN_ADAPTER_2(name, ret, t1, t2) \\""",
        "#define DEF_HELPER_FLAGS_3(name, flags, ret, t1, t2, t3)                \\":"""
         #define DEF_HELPER_FLAGS_3(name, flags, ret, t1, t2, t3)                \\
         GEN_ADAPTER_3(name, ret, t1, t2, t3) \\""",
        "#define DEF_HELPER_FLAGS_4(name, flags, ret, t1, t2, t3, t4)            \\":"""
         #define DEF_HELPER_FLAGS_4(name, flags, ret, t1, t2, t3, t4)            \\
         GEN_ADAPTER_4(name, ret, t1, t2, t3, t4) \\""",
        "#define DEF_HELPER_FLAGS_5(name, flags, ret, t1, t2, t3, t4, t5)        \\":"""
         #define DEF_HELPER_FLAGS_5(name, flags, ret, t1, t2, t3, t4, t5)        \\
         GEN_ADAPTER_5(name, ret, t1, t2, t3, t4, t5) \\""",
    })
    # Fix unaligned reads
    replace(os.path.join(UNICORN_QEMU_DIR, "tci.c"), {
        "static tcg_target_ulong tci_read_i(uint8_t **tb_ptr)":
        """
        static tcg_target_ulong tci_read_i(uint8_t **tb_ptr) {
            tcg_target_ulong value =
                *((*tb_ptr)+0) <<  0 |
                *((*tb_ptr)+1) <<  8 |
                *((*tb_ptr)+2) << 16 |
                *((*tb_ptr)+3) << 24;
            *tb_ptr += sizeof(value);
            return value;
        }
        static tcg_target_ulong tci_read_i_old(uint8_t **tb_ptr)
        """,

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

def compileUnicorn(targets):
    # Patching Unicorn's QEMU fork
    patchUnicornTCI()
    patchUnicornJS()

    # Emscripten: Make
    os.chdir('unicorn')
    os.system('make clean')
    if os.name == 'posix':
        cmd = ''
        if targets:
            cmd += 'UNICORN_ARCHS="%s" ' % (' '.join(targets))
        cmd += 'emmake make'
        os.system(cmd)
    os.chdir('..')

    # Compile static library to JavaScript
    cmd = 'emcc'
    cmd += ' -Os --memory-init-file 0'
    cmd += ' unicorn/libunicorn.a'
    cmd += ' -s EXPORTED_FUNCTIONS=\"[\''+ '\', \''.join(EXPORTED_FUNCTIONS) +'\']\"'
    cmd += ' -s ALLOW_MEMORY_GROWTH=1'
    cmd += ' -s MODULARIZE=1'
    cmd += ' -s EXPORT_NAME="\'MUnicorn\'"'
    if targets:
        cmd += ' -o src/libunicorn-%s.out.js' % ('-'.join(targets))
    else:
        cmd += ' -o src/libunicorn.out.js'
    os.system(cmd)


if __name__ == "__main__":
    # Initialize Unicorn submodule if necessary
    if not os.listdir(UNICORN_DIR):
        os.system("git submodule update --init")
    # Compile Unicorn
    targets = sys.argv[1:]
    if os.name in ['posix']:
        compileUnicorn(targets)
    else:
        print "Your operating system is not supported by this script:"
        print "Please, use Emscripten to compile Unicorn manually to src/unicorn.out.js"
