# benchmark_sqlite_params.py
#
# MIT License
# Copyright (c) 2022 Holger Joukl

"""Pretty naive timeit benchmark comparing SQLAlchemy insertion based on
prepared, parameterized statements for each row + column vs executemany.
"""

import os
import sys
import timeit

from sqlalchemy import (
        Column, MetaData, String, Table, create_engine, delete, func,
        select)
from sqlalchemy.orm import Session


def setup_db(connect_str, number_of_cols, number_of_rows, col_pad, row_pad):
    engine = create_engine(connect_str, echo=False)
    meta = MetaData()
    columns = [
        Column(f'col{i:0{col_pad}}', String(col_pad + row_pad + 8))
        for i in range(number_of_cols)
        ]
    mytable = Table('mytable', meta, *columns)
    meta.create_all(engine)
    return engine, mytable


def insert_values_params(session, table, rows, buffer_size):
    stmt_values_params_base = table.insert()
    buffer = []
    for row in rows:
        buffer.append(row)
        if len(buffer) >= buffer_size:
            stmt_values_params = stmt_values_params_base.values(buffer)
            session.execute(stmt_values_params)
            buffer = []
    if len(buffer) > 0:
        stmt_values_params = stmt_values_params_base.values(buffer)
        session.execute(stmt_values_params)
        buffer = []
    session.commit()


def insert_values_executemany(session, table, rows, buffer_size):
    stmt_executemany = table.insert()
    buffer = []
    for row in rows:
        buffer.append(row)
        if len(buffer) >= buffer_size:
            session.execute(stmt_executemany, buffer)
            buffer = []
    if len(buffer) > 0:
        session.execute(stmt_executemany, buffer)
        buffer = []
    session.commit()


def check_and_clean(
        session, table, number_of_rows, number_of_cols, timeit_number,
        timeit_repeat):
    count_stmt = select(func.count()).select_from(table)
    result = session.execute(count_stmt)
    count = result.all()[0][0]
    #print(f'{count_stmt}: {count}')
    assert count == timeit_repeat * timeit_number * number_of_rows
    last_row = session.query(table).order_by(table.c[0].desc()).first()
    last_row_val = last_row[-1]
    #print(f'last row/col value: {last_row_val}')
    assert last_row_val == f'row{number_of_rows-1}_col{number_of_cols-1}'
    session.execute(delete(table))
    session.commit()


def benchmark(
        connect_str, number_of_cols, number_of_rows, timeit_number,
        timeit_repeat, buffer_size):
    # a simple benchmark comparing insertion based on prepared, parameterized
    # statements for each row executemany vs
    col_pad = len(str(number_of_cols)) - 1
    row_pad = len(str(number_of_rows)) - 1

    engine, table = setup_db(
        connect_str, number_of_cols, number_of_rows, col_pad, row_pad)
    rows = [
        {
            col.name: f'row{r:0{row_pad}}_col{c:0{col_pad}}'
            for c, col in enumerate(table.columns)
        }
        for r in range(number_of_rows)
        ]

    timeit_globals = {
        'insert_values_params': insert_values_params,
        'insert_values_executemany': insert_values_executemany,
        'table': table,
        'rows': rows,
        'buffer_size': buffer_size,
        }

    print('\n----------------------------------------------------------')
    print(connect_str)
    print('----------------------------------------------------------')
    for stmt in [
            'insert_values_params(session, table, rows, buffer_size)',
            'insert_values_executemany(session, table, rows, buffer_size)']:

        with Session(engine) as session:
            # Make sure to start with an empty table
            session.execute(delete(table))
            timeit_globals['session'] = session
            res = timeit.repeat(
                stmt, repeat=timeit_repeat, number=timeit_number,
                globals=timeit_globals)
            check_and_clean(
                    session, table, number_of_rows, number_of_cols,
                    timeit_number, timeit_repeat)
            print(f'{stmt}')
            print(f'    results: {res}, best of {timeit_repeat}: {min(res)}')
            print(f'    (best of {timeit_repeat}: {min(res)},')
            print(f'     average: {sum(res)/timeit_repeat})')
            print('----------------------------------------------------------')

    with Session(engine) as session:
        table.drop(engine)


def parse_args(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--connect', help='SQLAlchemy connect string [%(default)s]',
        default='sqlite:///app.db')
    parser.add_argument(
        '-c', '--columns', type=int,
        help='Number of columns/fields [%(default)s]', default=90)
    parser.add_argument(
        '-r', '--rows', type=int, help='Number of rows [%(default)s]',
        default=100)
    parser.add_argument(
        '--buffer-size', type=int,
        help='Buffer size for data chunking [%(default)s]', default=1000)
    parser.add_argument(
        '--timeit-number', type=int, help='Timeit number arg [%(default)s]',
        default=1000)
    parser.add_argument(
        '--timeit-repeat', type=int, help='Timeit repeat arg [%(default)s]',
        default=3)
    args = parser.parse_args(argv)
    return args


def main(args=None):
    args = parse_args(argv=args)
    return benchmark(
            connect_str=args.connect,
            number_of_cols=args.columns,
            number_of_rows=args.rows,
            timeit_number=args.timeit_number,
            timeit_repeat=args.timeit_repeat,
            buffer_size=args.buffer_size)


if __name__ == '__main__':
    sys.exit(main())
