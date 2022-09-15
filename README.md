# bench-sqlalchemy-executemany
Naive timeit-based database benchmark of executemany vs prepared statements
with parameterization for every row value, through SQLAlchemy.

## Background
Prompted by https://github.com/frictionlessdata/framework/issues/1196 for the
great [frictionless framework](https://github.com/frictionlessdata/framework).

This issue raises the question if it's more performant for the database client
to use an `executemany` prepared statement vs a prepared statement using
"*parameters for each column, for each row*".

See https://docs.sqlalchemy.org/en/14/tutorial/dbapi_transactions.html#tutorial-multiple-parameters.

At the time of issue creation frictionless contains SQLAlchemy ORM code like
`connection.execute(sql_table.insert().values(rows))`. This creates a huge
"bulk insert" SQL statement:
```
INSERT INTO datatable (header0, header1, header2, header3, header4, header5,
header6, header7, header8, header9) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?), 
(?, ?, ?, ?, ?, ?, ?, ?, ?, ?), ...
```
I.e. this uses separate parameters *for each field, for each row*.
(which is why this runs in into problems for tables with (too) many columns
with SQLite since this has upper parameter limits, see issue).

In contrast, applying `executemany` with
`connection.execute(sql_table.insert(), rows)` generates

```
INSERT INTO datatable (header0, header1, header2, header3, header4, header5,
header6, header7, header8, header9) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

and applies the database engine's `executemany`.

## Preparations
A convenient way of running the benchmark script against SQLite, PostgreSQL and
MySQL is to use existing official db container images.
Not needed for SQLite since file-based and included in the Python standard
library, obviously.

Note that we absolutely don't care about security here, using plaintext secrets
on the command line, using weak passwords, etc.
You don't do this for any real work, **do you**?

### Create venv for running the benchmark script
```
# Create venv.
python3 -m venv .venv

# Activate venv.
source .venv/bin/activate

# Upgrade venv installation machinery.
pip install --upgrade pip setuptools wheel

# Install orm and db drivers.
pip install sqlalchemy>=1.3 psycopg2 pymysql
```

### Pull DB container images

```
docker pull postgres
docker pull mysql:8
```

### Start DB containers

#### PostgreSQL
```
# Create db storage location.
mkdir -p "$HOME/data/postgres"

# Start container.
# Using *relative* PGDATA sub-path avoids a permission problem with directory
# creation (will result in paths /var/lib/postgresql/data/pgdata inside the
# container and $HOME/data/postgres/pgdata on the host machine)
docker run -d -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e \
    POSTGRES_DB=postgres_db -e PGDATA=pgdata -p 5432:5432 \
    -v $HOME/data/postgres:/var/lib/postgresql/data --name postgresql postgres

# Optionally check container logs.
#docker logs postgresql
```

#### MySQL

```
# Start container.
docker run --detach -e MYSQL_ROOT_PASSWORD=mysqlroot -e MYSQL_USER=mysql \
    -e MYSQL_PASSWORD=mysql --name=mysql1 --restart on-failure \
    --publish 3306:3306 -d mysql:8

# Optionally check container logs.
#docker logs postgresql

# Create test db.
mysql -umysql -pmysql -h127.0.0.1 -P3306 -e 'create database test'

# Optionally show users.
#mysql -uroot -pmysqlroot -h127.0.0.1 -P3306 -e 'SELECT User, Host FROM mysql.user;

# Grant sufficient rights to mysql user.
mysql -uroot -pmysqlroot -h127.0.0.1 -P3306 -e "GRANT CREATE, ALTER, DROP, INSERT, UPDATE, DELETE, SELECT, REFERENCES, RELOAD on *.* TO 'mysql';"
```

## Running the benchmark script
Simply run the benchmark using an SQLAlchemy DB connect string. You can use
Python timeit parameters and influence the number of columns and rows, see

```
python benchmark_sqlite_params.py --help
```

See https://docs.sqlalchemy.org/en/14/core/engines.html for SQLAlchemy connect
string syntax for different db dialects.

SQLite example:
```
rm -f app.db && 
    python benchmark_sqlite_params.py -c 10 -r 10 --timeit-number 100 \
        --timeit-repeat 5 --connect "sqlite:///app.db" 
```


## Sample run results

Here are some results of a sample run using 10000 rows with 20 columns.

Invocation:
```
(rm -f app.db;
for CONN in "sqlite:///app.db" \
    "postgresql+psycopg2://postgres:postgres@localhost/postgres_db" \
    "mysql+pymysql://mysql:mysql@localhost:3306/test"; do
        python benchmark_sqlite_params.py -c 20 -r 10000 --timeit-number 100 \
        --timeit-repeat 5 --connect "$CONN";
done)
```

Output:
```
----------------------------------------------------------
sqlite:///app.db
----------------------------------------------------------
insert_values_params(session, table, rows, buffer_size)
    results: [209.7843231470033, 221.26734708700678, 217.42528593199677, 214.6778446380049, 216.28287990999524], best of 5: 209.7843231470033
    (best of 5: 209.7843231470033,
     average: 215.8875361428014)
----------------------------------------------------------
insert_values_executemany(session, table, rows, buffer_size)
    results: [9.965977744024713, 10.167907252995064, 10.199459975992795, 10.204026395978872, 10.584025154006667], best of 5: 9.965977744024713
    (best of 5: 9.965977744024713,
     average: 10.224279304599623)
----------------------------------------------------------

----------------------------------------------------------
postgresql+psycopg2://postgres:postgres@localhost/postgres_db
----------------------------------------------------------
insert_values_params(session, table, rows, buffer_size)
    results: [288.6309609169839, 293.43941178600653, 293.338221271988, 291.42929303398705, 292.72071425200556], best of 5: 288.6309609169839
    (best of 5: 288.6309609169839,
     average: 291.9117202521942)
----------------------------------------------------------
insert_values_executemany(session, table, rows, buffer_size)
    results: [68.01096502097789, 68.52964984602295, 67.75875709002139, 66.14020613598404, 65.73387462401297], best of 5: 65.73387462401297
    (best of 5: 65.73387462401297,
     average: 67.23469054340384)
----------------------------------------------------------

----------------------------------------------------------
mysql+pymysql://mysql:mysql@localhost:3306/test
----------------------------------------------------------
insert_values_params(session, table, rows, buffer_size)
    results: [279.095519658993, 280.00763399599236, 279.11239849802223, 281.00181985500967, 278.0900102739979], best of 5: 278.0900102739979
    (best of 5: 278.0900102739979,
     average: 279.46147645640303)
----------------------------------------------------------
insert_values_executemany(session, table, rows, buffer_size)
    results: [331.7496841799875, 253.69587833201513, 61.01600893199793, 61.68035774800228, 60.267170513019664], best of 5: 60.267170513019664
    (best of 5: 60.267170513019664,
     average: 153.6818199410045)
----------------------------------------------------------
```

Take this with a grain of salt: No effort whatsoever have been made to make
this "stable", i.e. no
- system tuning,
- cpu affinity setting,
- process priority setting or
- removing any other noise happening elsewhere on the computer.

:-)

But I still think this gives a clear indication that performance-wise, using
`executemany` is vastly superior to the "*separate parameter for each field,
for each row*" approach, for the tested database engines (Python stdlib
sqlite, PostgreSQL with psycopg, MySQL with pymysql).

## Further optimization?
Note that the benchmark script implementation applies some "buffer chunking"
for the given data rows in batches of 1000, leaning on the current frictionless
implementation. This can be changed through the `--buffer-size` command line
parameter. So it would be possible to run the benchmark with different buffer
sizes to (maybe) tune performance.

I'd expect this to be dependent on the database engine & driver and haven't
looked into it.
