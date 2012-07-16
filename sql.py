import sqlite3, types
import numpy as np
from pwtools import common
from itertools import izip
import os

def get_test_db():
    db = SQLiteDB(':memory:', table='calc')
    db.create_table([('a', 'TEXT'), ('b', 'FLOAT')])
    db.execute("insert into calc (a,b) values ('lala', 1.0)")
    db.execute("insert into calc (a,b) values ('huhu', 2.0)")
    db.commit()
    return db

def find_sqltype(val):
    mapping = {\
        types.NoneType:    'NULL',
        types.IntType:     'INTEGER',
        types.LongType:    'INTEGER',
        types.FloatType:   'REAL',  # 'FLOAT' also works
        types.StringTypes: 'TEXT',  # StringType + UnicodeType
        types.BufferType:  'BLOB'}
    for typ in mapping.keys():
        if isinstance(val, typ):
            return mapping[typ]
    raise StandardError("type '%s' unknown, cannot find mapping "
        "to sqlite3 type" %str(type(val)))

def fix_sqltype(sqltype):
    st = sqltype.upper()
    if st == 'FLOAT':
        st = 'REAL'
    return st        

def fix_sql_header(header):
    return [(x[0], fix_sqltype(x[1])) for x in header]


class SQLEntry(object):
    def __init__(self, sqlval=None, sqltype=None, fileval=None, key=None):
        """Represent an entry in a SQLite database. An entry is one single
        value of one column and record (record = row). 
        
        This class is ment to be used in parameter studies where a lot of
        parameters are vaired (e.g. in pw.x input files) and entered in a
        SQLite database. 
        
        There is the possibility that the entry has a slightly different value
        in the db and in the actual input file. See fileval.
        
        args:
        -----
        sqlval : Any Python type (str, unicode, float, integer, ...)
            The value of the entry which is entered into the database. The
            sqlite3 module 
        sqltype : {str, None}, optional
            A string (not case sentitive) which determines the sqlite type of the
            entry: 'integer', 'real', 'null', ... If None then automatic type
            detection will be attempted. Only default types are supported, see
            notes below. This is needed to create a sqlite table like in 
                create table calc (foo integer, bar real)
        fileval : {None, <anything>}, optional
            If not None, then this is the value of the entry that it has in
            another context (actually used in the input file). If None, then
            fileval = val. 
            Example: K_POINTS in pw.x input file:
                sqlval: '2 2 2 0 0 0'
                fileval: 'K_POINTS automatic\n2 2 2 0 0 0'
        key : optional, {None, str}, optional
            An optional key. This key should refer to the column name in the 
            database table, as in:
                % create table calc (key1 sqltype1, key2 sqltype2, ...)
            For example:
                % create table calc (idx integer, ecutwfc float, ...)

        notes:
        ------
        SQLite types from the Python docs of sqlite3:
            Python type     SQLite type
            -----------     -----------
            None            NULL
            int             INTEGER
            long            INTEGER
            float           REAL
            str (UTF8-encoded)  TEXT
            unicode         TEXT
            buffer          BLOB
        """
        self.sqltype = find_sqltype(sqlval) if sqltype is None else \
                       fix_sqltype(sqltype)
        self.sqlval = sqlval
        self.fileval = sqlval if fileval is None else fileval
        self.key = key


class SQLiteDB(object):
    """Small convenience inerface class for sqlite3. It abstacts away the
    connecting to the database etc. It simplifies the usage of connection and
    cursor objects (bit like the "shortcuts" already defined in sqlite3).   
    
    Currently, we assume that the db has one table only, therefore we
    enforce `table` in the constructor.

    exported methods:
    -----------------
    self.cur.execute() -> execute()
    self.conn.commit() -> commit()
    where self.cur  -> sqlite3.Cursor
          self.conn -> sqlite3.Connection
    
    example:
    --------
    >>> db = SQLiteDB('test.db', table='calc')
    >>> db.create_table([('a', 'float'), ('b', 'text')])
    >>> db.execute("insert into %s ('a', 'b') values (1.0, 'lala')" %db.table)
    >>> db.execute("insert into %s ('a', 'b') values (?,?)" %db.table, (2.0, 'huhu'))
    # iterator
    >>> for record in db.execute("select * from calc"):
    ...     print record
    (1.0, u'lala')
    (2.0, u'huhu')
    # list
    >>> print db.execute("select * from calc").fetchall()
    [(1.0, u'lala'), (2.0, u'huhu')]
    >>> db.get_list1d("select a from calc")
    [1.0, 2.0]
    >>> db.get_list1d("select b from calc")
    [u'lala', u'huhu']
    >>> db.get_array1d("select a from calc")
    array([ 1.,  2.])
    >>> db.add_column('c', 'float')
    >>> db.execute("update calc set c=5.0")
    >>> db.get_array("select a,c from calc")
    array([[ 1.,  5.],
           [ 2.,  5.]])
    
    notes:
    ------
    There are actually 2 methods to put entries into the db. Fwiw, this is a
    general sqlite3 (module) note.

    1) Use sqlite3 placeholder syntax. This is recommended. Here, automatic
       type conversion Python -> sqlite is done by the sqlite3 module. For
       instance, double numbers (i.e. Python float type) will be correctly
       stored as double by SQLite default.
       
       >>> db.execute("insert into calc ('a', 'b') values (?,?)", (1.0, 'lala'))
    
    2) Write values directly into sql command. Here all values are actually
       strings.        
       >>> db.execute("insert into calc ('a', 'b') values (1.0, 'lala')")
       >>> db.execute("insert into calc ('a', 'b') values (%e, '%s')" %(1.0, 'lala')")
       
       There are some caveats. For example, the string ('lala' in the example)
       must appear *qsingle-quoted* in the sqlite cmd to be recognized as such.
       Also aviod things like `"... %s" %str(1.0)`. This will truncate the
       float after less then 16 digits and thus store the 8-byte float with
       less precision! 
    """
    def __init__(self, db_fn, table=None):
        """
        args:
        -----
        db_fn : str
            database filename
        table : str, optional
            name of the database table
        """            
        self.db_fn = db_fn
        self.conn = sqlite3.connect(db_fn)
        self.cur = self.conn.cursor()
        self.table = table
        if self.table is None:
            raise StandardError("table missing")
    
    def set_table(self, table):
        """Set the table name (aka switch to another table).

        args:
        -----
        table : str
            table name
        """            
        self.table = table
    
    def get_table(self):
        return self.table

    def execute(self, *args, **kwargs):
        """This calls self.cur.execute()"""
        return self.cur.execute(*args, **kwargs)
    
    def has_table(self, table):
        """Check if a table named `table` already extists."""
        assert table is not None, ("table is None")
        return self.execute("pragma table_info(%s)" %table).fetchall() != []

    def has_column(self, col):
        """Check if table self.table already has the column `col`.
        
        args:
        -----
        col : str
            column name in the database
        """            
        for entry in self.get_header():
            if entry[0] == col:
                return True
        return False                
    
    def add_column(self, col, sqltype):
        """Add column `col` with type `sqltype`. 
        
        args:
        -----
        col : str
            column name
        sqltype : str
            sqlite data type (see SQLEntry)
        """
        if not self.has_column(col):
            self.execute("ALTER TABLE %s ADD COLUMN %s %s" \
                        %(self.table, col, fix_sqltype(sqltype)))
    
    def add_columns(self, header):
        """Convenience function to add multiple columns from `header`. See
        get_header().
        
        example:
        --------
        >>> db.add_columns([('a', 'text'), ('b', 'real')])
        # is the same as
        >>> db.add_column('a', 'text')
        >>> db.add_column('b', 'real')
        """
        for entry in fix_sql_header(header):
            self.add_column(*entry)
    
    def get_max_rowid(self):
        """Return max(rowid), which is equal to the number of rows in
        self.table ."""
        return self.get_single("select max(rowid) from %s" %self.table)

    def fill_column(self, col, values, start=1, extend=True, overwrite=False):
        """Fill existing column `col` with values from `values`, starting from
        rowid `start`. "rowid" is a special sqlite column which is always
        present and which numbers all rows. 

        The column must already exist. To add a new column and fill it, see
        attach_column().
        
        args:
        -----
        col : str
            Column name.
        values : sequence
            Values to be inserted.
        start : int
            sqlite rowid value to start at (first row: start=1)
        extend : If `extend=True` and `len(values)` extends the last row, then
            continue to add values. All other column entries will be NULL. If
            False, then we silently stop inserting at the last row.
        overwrite : bool
            Whether to overwrite entries which are not NULL (None in Python).
        """
        # The operation "update <table> ..." works only as long as there is at
        # least one column with a non-NULL entry. After that, rowid is not
        # defined and nothing gets inserted. Then, we need to use "insert into
        # ..." to appand rows to the bottom.
        maxrowid = self.get_max_rowid()
        assert self.has_column(col), "column missing: %s" %col
        if not extend:
            assert start <= maxrowid, "start > maxrowid"
        rowid = start
        for val in values:
            if rowid <= maxrowid:
                if not overwrite:
                    _val = self.get_single("select %s from %s where rowid==?" \
                            %(col, self.table), (rowid,))
                    assert _val is None, ("value for column '%s' at rowid "
                        "%i is not NULL (%s)" %(col, rowid, repr(_val)))
                self.execute("update %s set %s=? where rowid==?" \
                             %(self.table, col), (val, rowid))
            else:
                if extend:
                    self.execute("insert into %s (%s) values (?)" %(self.table,
                        col,), (val,))
            rowid += 1                
    
    def attach_column(self, col, values, sqltype=None, **kwds):
        """Attach (add) a new column named `col` of `sqltype` and fill it with
        `values`. With overwrite=True, allow writing into existing columns,
        i.e. behave like fill_column().
        
        This is a short-cut method which essentially does:
            add_column(...)
            fill_column(...)

        args:
        -----
        col : str
            Column name.
        values : sequence
            Values to be inserted.
        sqltype : str, optional
            sqlite type of values in `values`, obtained from values[0] if None
        **kwds : additional keywords passed to fill_column(),
            default: start=1, extend=True, overwrite=False
        """
        current_kwds = {'start':1, 'extend': True, 'overwrite': False}
        current_kwds.update(kwds)
        if not current_kwds['overwrite']:
            assert not self.has_column(col), ("column already present: %s, use " 
                                              "overwrite=True" %col)
        if sqltype is None:
            sqltype = find_sqltype(values[0])
        self.add_column(col, sqltype)
        self.fill_column(col, values, **current_kwds)

    def get_header(self):
        """Return the "header" of the table `table':

        example:
        --------
        >>> db = SQLiteDB('test.db', table='foo')
        >>> db.execute("create table foo (a text, b real)"
        >>> db.get_header() 
        [('a', 'text'), ('b', 'real')]
        """
        return [(x[1], x[2]) for x in \
                self.execute("PRAGMA table_info(%s)" %self.table)]
    
    def create_table(self, header):
        """Create a table named self.table from `header`. `header` is in the
        same format which get_header() returns.
        
        args:
        -----
        header : list of lists/tuples
            [(colname1, sqltype1), (colname2, sqltype2), ...]
        """
        self.execute("CREATE TABLE %s (%s)" %(self.table, 
                                            ','.join("%s %s" %(x[0], x[1]) \
                                            for x in fix_sql_header(header))))
    
    def get_list1d(self, *args, **kwargs):
        """Shortcut for commonly used functionality: If one extracts a single
        column, then self.cur.fetchall() returns a list of tuples like 
            [(1,), (2,)]. 
        We call fetchall() and return the flattened list. 
        """
        return common.flatten(self.execute(*args, **kwargs).fetchall())
    
    def get_single(self, *args, **kwargs):
        """Return single entry from the table."""
        ret = self.get_list1d(*args, **kwargs)
        assert len(ret) > 0, ("nothing returned")
        assert len(ret) == 1, ("no unique result")
        return ret[0]

    def get_array1d(self, *args, **kwargs):
        """Same as get_list1d, but return numpy array."""
        return np.array(self.get_list1d(*args, **kwargs))
    
    def get_array(self, *args, **kwargs):
        """Return result of self.execute().fetchall() as numpy array. 
        
        Usful for 2d arrays, i.e. convert result of extracting >1 columns to
        numpy 2d array. The result depends on the data types of the columns."""
        return np.array(self.execute(*args, **kwargs).fetchall())
    
    def get_dict(self, *args, **kwargs):
        """For the provided select statement, return a dict where each key is
        the column name and the column is a list. Column names are obtained
        from the Cursor.description attribute.

        "select foo,bar from calc" would return
        {'foo': [1,2,3],
         'bar': ['x', 'y', 'z']}
        """
        cur = self.execute(*args, **kwargs)
        # ['col0', 'col1, ...]
        cols = [entry[0] for entry in cur.description]
        # [(val0_0, val0_1, ...), # row 0
        #  (val1_0, val1_1, ...), # row 1
        #  ...]
        ret = cur.fetchall()
        dct = dict((col, []) for col in cols)
        # {'col0': [val0_0, val1_0, ...], 
        #  'col1': [val0_1, val1_1, ...], 
        #  ...}
        for row in ret:
            for idx, col in enumerate(cols):
                dct[col].append(row[idx])
        return dct                

    def commit(self):
        self.conn.commit()
    
    def finish(self):
        self.commit()
        self.cur.close()

    def __del__(self):
        self.finish()


# XXX old behavior in argument list: key, sqltype, lst. If you want this, then
# either replace sql_column -> sql_column_old in your script or explitely use 
# sql_column(key=..., sqltype=..., lst=...).
def sql_column_old(key, sqltype, lst, sqlval_func=lambda x: x, fileval_func=lambda x: x):
    """
    example:
    --------
    >>> _vals = [25,50,75]
    >>> vals = sql_column('ecutfwc', 'float', _vals, 
    ...                   fileval_func=lambda x: 'ecutfwc=%s'%x)
    >>> for v in vals:
    ...     print v.key, v.sqltype, v.sqlval, v.fileval
    ecutfwc float 25 ecutfwc=25
    ecutfwc float 50 ecutfwc=50
    ecutfwc float 75 ecutfwc=75
    """
    return [SQLEntry(key=key, 
                     sqltype=sqltype, 
                     sqlval=sqlval_func(x), 
                     fileval=fileval_func(x)) for x in lst]


def sql_column(key, lst, sqltype=None, sqlval_func=lambda x: x, fileval_func=lambda x: x):
    """Convert a list `lst` of values of the same type (i.e. all floats) to a
    list of SQLEntry instances of the same column name `key` and `sqltype`
    (e.g. 'float'). 

    See ParameterStudy for applications.
     
    args:
    -----
    key : str
        sql column name
    lst : sequence of arbitrary values, these will be SQLEntry.sqlval
    sqltype : str, optional
        sqlite type, if None then it is determined from the first entry in
        `lst` (possibly modified by sqlval_func)
    sqlval_func : callable, optional
        Function to transform each entry lst[i] to SQLEntry.sqlval
        Default is sqlval = lst[i].
    fileval_func : callable, optional
        Function to transform each entry lst[i] to SQLEntry.fileval
        Default is fileval = lst[i].
        example:
            lst[i] = '23'
            fileval = 'value = 23'
            fileval_func = lambda x: "value = %s" %str(x)
    
    example:
    --------
    >>> vals = sql_column('ecutfwc', [25.0, 50.0, 75.0], 
    ...                   fileval_func=lambda x: 'ecutfwc=%s'%x)
    >>> for v in vals:
    ...     print v.key, v.sqltype, v.sqlval, v.fileval
    ecutfwc REAL 25.0 ecutfwc=25.0 
    ecutfwc REAL 50.0 ecutfwc=50.0
    ecutfwc REAL 75.0 ecutfwc=75.0
    """
    sqlval_lst = [sqlval_func(x) for x in lst]
    fileval_lst = [fileval_func(x) for x in lst]
    types = [type(x) for x in sqlval_lst]
    assert len(set(types)) == 1, ("after sqlval_func(), not all entries in "
        "sqlval_lst have the same type: %s" %str(types))
    _sqltype = find_sqltype(sqlval_lst[0]) if sqltype is None \
        else sqltype.upper()
    return [SQLEntry(key=key, 
                     sqltype=_sqltype, 
                     sqlval=sv, 
                     fileval=fv) for sv,fv in \
                        izip(sqlval_lst, fileval_lst)]


def sql_matrix(lists, header=None, colnames=None, sqlval_funcs=None, fileval_funcs=None):
    """Convert each entry in a list of lists ("matrix" = sql table) to an
    SQLEntry based on `header`. This can be used to quickly convert the result
    of comb.nested_loops() (nested lists) to input `params_lst` for
    ParameterStudy.
    
    The entries in the lists can have arbitrary values, but each "column"
    should have the same type. Each sublist (= row) can be viewed as a record in
    an sql database, each column as input for sql_column().
    
    If you provide `header`, then tyes for each column are taken from that. If
    `colnames` are used, then types are fetched (by find_sqltype()) from the
    first row. May not work for "incomplete" datasets, where some entries in
    the first row are None (NULL in sqlite).

    args:
    -----
    lists : list of lists 
    header : sequence, optional 
        [('foo', 'integer'), ('bar', 'float'), ...], see
        sql.SQLiteDB
    colnames : sequence os strings, optional
        Use either `colnames` or `header`.
    sqlval_funcs, fileval_funcs: {None, dict}
        For certain (or all) columns, you can specify a sqlval_func /
        fileval_func. They have the same meaning as in sql_column().
        E.g. sql_matrix(..., fileval_funcs={'foo': lambda x: str(x)+'-value'})
        would set fileval_func for the whole column 'foo'.
    
    returns:
    --------
    list of lists

    example:
    --------
    >>> lists=comb.nested_loops([[1.0,2.0,3.0], zip(['a', 'b'], [888, 999])],
    ...                         flatten=True)
    >>> lists
    [[1.0, 'a', 888],
     [1.0, 'b', 999],
     [2.0, 'a', 888],
     [2.0, 'b', 999],
     [3.0, 'a', 888],
     [3.0, 'b', 999]]
    >>> header=[('col0', 'float'), ('col1', 'text'), ('col2', 'integer')]
    >>> m=batch.sql_matrix(lists, header)
    >>> for row in m:
    ...     print [(xx.key, xx.fileval) for xx in row]
    ...
    [('col0', 1.0), ('col1', 'a'), ('col2', 888)]
    [('col0', 1.0), ('col1', 'b'), ('col2', 999)]
    [('col0', 2.0), ('col1', 'a'), ('col2', 888)]
    [('col0', 2.0), ('col1', 'b'), ('col2', 999)]
    [('col0', 3.0), ('col1', 'a'), ('col2', 888)]
    [('col0', 3.0), ('col1', 'b'), ('col2', 999)]
    >>> m=batch.sql_matrix(lists, header, fileval_funcs={'col0': lambda x: x*100})
    >>> for row in m:
    ...     print [(xx.key, xx.fileval) for xx in row]
    ...
    [('col0', 100.0), ('col1', 'a'), ('col2', 888)]
    [('col0', 100.0), ('col1', 'b'), ('col2', 999)]
    [('col0', 200.0), ('col1', 'a'), ('col2', 888)]
    [('col0', 200.0), ('col1', 'b'), ('col2', 999)]
    [('col0', 300.0), ('col1', 'a'), ('col2', 888)]
    [('col0', 300.0), ('col1', 'b'), ('col2', 999)]
    """
    if header is None:
        assert colnames is not None, ("colnames is None")
        sqltypes = [find_sqltype(xx) for xx in lists[0]]
        header = zip(colnames, sqltypes)
    ncols = len(header)
    ncols2 = len(lists[0])
    keys = [entry[0] for entry in header]
    assert ncols == ncols2, ("number of columns differ: lists (%i), "
        "header (%i)" %(ncols2, ncols))
    _sqlval_funcs = dict([(key, lambda x: x) for key in keys])
    _fileval_funcs = dict([(key, lambda x: x) for key in keys])
    if sqlval_funcs is not None:
        _sqlval_funcs.update(sqlval_funcs)
    if fileval_funcs is not None:
        _fileval_funcs.update(fileval_funcs)
    newlists = []        
    for row in lists:
        newrow = []
        for ii, entry in enumerate(row):
            key = header[ii][0]
            sqltype = header[ii][1]
            newrow.append(SQLEntry(key=key,
                                   sqltype=sqltype,
                                   sqlval=_sqlval_funcs[key](entry),
                                   fileval=_fileval_funcs[key](entry)))
        newlists.append(newrow)                                   
    return newlists   

def makedb(filename, lists=None, colnames=None, table=None, mode='a', **kwds):
    """ Create sqlite db `filename` (mode='w') or append to existing db
    (mode='a'). The database is build up from `lists` and `colnames`, see 
    sql_matrix().

    In append mode, rows are simply added to the bottom of the table and only
    column names (`colnames`) which are already in the table are allowed.
    `colnames` can contain a subset of the original header, in which case the
    other entries are NULL by default.

    If the datsbase file doesn't exist, then mode='a' is the same as mode='w'.

    args:
    -----
    lists : list of lists, see sql_matrix()
    colnames : list of column names, see sql_matrix()
    table : str, optional
        String with table name. If None then we try to set a default name based
        in `filename`.
    mode : str
        'w': write new db, 'a': append
    **kwds : passed to sql_matrix()
    """
    sufs = ['.db', '.sqlite', '.sqlite3']
    for suffix in sufs:
        if filename.endswith(suffix):
            table = os.path.basename(filename.replace(suffix, ''))
            break
    assert table is not None, ("table name missing or could not determine "
                               "from filename")
    assert len(colnames) == len(lists[0]), ("len(colnames) != length of "
                                            "first list")        
    if mode == 'w':        
        if os.path.exists(filename):
            os.remove(filename)
    sqltypes = [find_sqltype(xx) for xx in lists[0]]
    header = zip(colnames, sqltypes)
    db = SQLiteDB(filename, table=table)
    if not db.has_table(table):
        db.create_table(header)
    else:
        db_header = db.get_header()
        db_colnames = [x[0] for x in db_header]
        db_types = [x[1] for x in db_header]
        for col,typ in header:
            assert col in db_colnames, ("col '%s' not in db header" %col)
            db_typ = db_types[db_colnames.index(col)]
            assert typ == db_typ, ("col: '%s': "
                "types differ, db: '%s', here: '%s'" %(col, db_typ, typ))
    sql_lists = sql_matrix(lists, header=header, **kwds)
    for row in sql_lists:
        ncols = len(row)
        names = ','.join(colnames)
        values = ','.join(['?']*ncols)
        cmd = 'insert into %s (%s) values (%s)' %(table, names, values)
        db.execute(cmd, [entry.sqlval for entry in row])
    db.finish() 
    return db
