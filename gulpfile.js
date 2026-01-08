const gulp = require("gulp");
const sass = require("gulp-sass")(require("sass"));
var browserSync = require("browser-sync").create();

const paths = {
  styles: {
    srcMain: "project/static/scss/main.scss",
    src: "project/static/scss/*.scss",
    dest: "project/static/css",
  },
};

gulp.task("browser-sync", function () {
  browserSync.init({
    proxy: "127.0.0.1:5001",
    open: "external",
    port: 3000,
  });
});

gulp.task("sass", function () {
  return gulp
    .src(paths.styles.srcMain)
    .pipe(sass().on("error", sass.logError))
    .pipe(gulp.dest(paths.styles.dest));
});

gulp.task("watch", function () {
  gulp.watch(
    paths.styles.src,
    gulp.series("sass", function (done) {
      browserSync.reload();
      done();
    })
  );
});

gulp.task(
  "default",
  gulp.series("sass", gulp.parallel("browser-sync", "watch"))
);
