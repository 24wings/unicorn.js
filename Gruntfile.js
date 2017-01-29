'use strict';

module.exports = function (grunt) {
    // Load tasks from grunt-* dependencies in package.json
    require('load-grunt-tasks')(grunt);

    // Time how long tasks take
    require('time-grunt')(grunt);

    // Project configuration
    grunt.initConfig({
        exec: {
            emscripten: {
                command: 'python build.py'
            }
        },
        uglify: {
            dist: {
                options: {
                    compress: true,
                },
                files: {
                    'dist/unicorn.min.js': [
                        'src/**/*.js'
                    ]
                }
            }
        },
        concat: {
            dist: {
                src: [
                    'src/libunicorn.out.js',
                    'src/unicorn.js',
                    'src/unicorn-arm.js',
                    'src/unicorn-arm64.js',
                    'src/unicorn-m68k.js',
                    'src/unicorn-mips.js',
                    'src/unicorn-sparc.js',
                    'src/unicorn-x86.js',
                ],
                dest: 'dist/unicorn.min.js'
            }
        },
        connect: {
            options: {
                port: 9001,
                livereload: 35729,
                hostname: 'localhost'
            },
            livereload: {
                options: {
                    open: true
                }
            }
        },
        watch: {
            building: {
                files: [
                    'src/*.js',
                ],
                tasks: ['concat'],
            },
            livereload: {
                files: [
                    '*.html',
                    '*.css',
                    '*.js',
                    'demos/*.html',
                    'demos/*.css',
                    'demos/*.js',
                    'dist/*.js',
                ],
                options: {
                    livereload: '<%= connect.options.livereload %>'
                }
            },
        }
    });

    // Project tasks
    grunt.registerTask('build', [
        'exec:emscripten',
        'concat'
    ]);
    grunt.registerTask('serve', [
        'connect',
        'watch'
    ]);
    grunt.registerTask('default', [
        'build'
    ]);
};
