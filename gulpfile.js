var gulp = require("gulp");
var browserSync = require("browser-sync").create();
var less = require("gulp-less");

const paths = {
  styles: {
    srcMain: "project/static/less/main.less",
    src: "project/static/less/*.less",
    dest: "project/static/css",
  },
};

function css() {
  return gulp
    .src(paths.styles.srcMain)
    .pipe(less())
    .pipe(gulp.dest(paths.styles.dest));
}

function watch() {
  gulp.watch(paths.styles.src, css);
}

exports.css = css;
exports.default = watch;
