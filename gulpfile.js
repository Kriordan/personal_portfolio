var gulp = require('gulp');
var browserSync = require('browser-sync').create();
var less = require('gulp-less');

gulp.task('serve', ['less'], function() {

    browserSync.init({
        proxy: "localhost:5000"
    });

    gulp.watch("static/less/*.less", ['less']);
    gulp.watch("templates/*.html").on("change", browserSync.reload);
});

gulp.task('less', function() {
    return gulp.src("project/static/less/main.less")
        .pipe(less())
        .pipe(gulp.dest("project/static/css"))
        .pipe(browserSync.stream());
});

gulp.task('default', ['serve']);
