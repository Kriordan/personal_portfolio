#!/bin/bash

#TODO: This doesn't handle test databases correctly
RESULT=`psql -l | grep "personalportfolio" | wc -l | awk '{print $1}'`;
if test $RESULT -eq 0; then
    echo "Creating Database";
    psql -c "create role personalportfolio with createdb encrypted password 'personalportfolio' login;"
    psql -c "alter user personalportfolio superuser;"
    psql -c "create database personalportfolio with owner personalportfolio;"
else
    echo "Database exists"
fi

#run initial setup of database tables
# poetry run python manage.py migrate
