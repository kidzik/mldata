"""
Convert from and to HDF5 (spec of mldata.org); and other utility functions
around HDF5.
"""


import h5py, numpy, os, sys
from scipy.sparse import csc_matrix
#from decimal import Decimal, InvalidOperation
from h5_arff import ARFF2H5, H52ARFF
from h5_libsvm import LibSVM2H5, H52LibSVM
from h5_uci import UCI2H5
from h5_csv import CSV2H5, H52CSV
from h5_mat import MAT2H5, H52MAT
from h5_octave import OCTAVE2H5, H52OCTAVE
import base


EPSILON = 1e-15
TOH5 = {
    'libsvm': LibSVM2H5,
    'arff': ARFF2H5,
    'uci': UCI2H5,
    'csv': CSV2H5,
    'matlab': MAT2H5,
    'octave' : OCTAVE2H5
}
FROMH5 = {
    'libsvm': H52LibSVM,
    'arff': H52ARFF,
    'csv': H52CSV,
    'matlab': H52MAT,
    'octave': H52OCTAVE
}



class ConversionError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class HDF5():
    def __init__(self, *args, **kwargs):
        """Construct an HDF5 object.

        The object can convert, extract data, create task
        files and more.

        @ivar converter: actual converter object
        @type converter: depending on required conversion, e.g. ARFF2H5.
        """
        self.converter = None


    def _compare(self, A, B):
        """Compare given lists A and B.

        @param A: list A to compare
        @type A: list of list
        @param B: list B to compare
        @type B: list of list
        """
#        eps_dec = Decimal(str(EPSILON))
        xrange_A0 = xrange(len(A[0]))
        for i in xrange(len(A)):
            Ai = A[i]
            Bi = B[i]
            for j in xrange_A0:
                try:
#                    a = Decimal(str(Ai[j]))
#                    b = Decimal(str(Bi[j]))
#                    if abs(a - b) > eps_dec:
                    if abs(Ai[j] - Bi[j]) > EPSILON:
                        return False
                except TypeError: #string
                    if str(Ai[j]) != str(Bi[j]):
                        return False
#                except InvalidOperation: # string
#                    if str(Ai[j]) != str(Bi[j]):
#                        return False
        return True


    def verify(self, fname_h5, fname_other, format_other):
        """Verify that data in given filenames is the same.

        @param fname_h5: name of H5 file to verify
        @type fname_h5: string
        @param fname_other: name of file to verify against
        @type fname_other: string
        @param format_other: format of other file
        @type format_other: string
        @raises: ConversionError
        """
        h5 = FROMH5[format_other](fname_h5, fname_other, remove_out=False).get_contents()
        other = TOH5[format_other](fname_other, fname_h5, remove_out=False).get_contents()

        # join individual vectors/matrices in other
        # the need to construct this seems really inefficient - maybe should
        # reconsider what get_contents() returns.
        if 'indptr' in other['data']: # sparse:
            other['data'] = csc_matrix(
                (other['data']['data'], other['data']['indices'], other['data']['indptr'])
                ).todense().tolist()
        else:
            data = []
            for name in other['ordering']:
                if name == 'label': continue
                if type(other['data'][name]) == numpy.matrix:
                    for row in other['data'][name]:
                        data.append(row.tolist()[0])
                else:
                    data.append(other['data'][name])
            other['data'] = numpy.matrix(data).T.tolist()

        if 'label' in h5['data']:
            if not self._compare(h5['label'], other['label']):
                raise ConversionError(
                    'Verification failed! Labels of %s != %s' % (fname_h5, fname_other)
                )

        if not self._compare(h5['data'], other['data']):
            raise ConversionError(
                'Verification failed! Data of %s != %s' % (fname_h5, fname_other)
            )


    def convert(self, in_fname, in_format, out_fname, out_format, seperator=None, verify=False):
        """Convert to/from HDF5.

        @param in_fname: name of in-file
        @type in_fname: string
        @param in_format: format of in-file
        @type in_format: string
        @param out_fname: name of out-file
        @type out_fname: string
        @param out_format: format of out-file
        @type out_format: string
        @param seperator: seperator to seperate variables in examples
        @type seperator: string
        @param verify: verify if data in output is same as data in input
        @type verify: boolean
        """
        self.converter = None
        try:
            if out_format == 'h5':
                self.converter = TOH5[in_format](in_fname, out_fname)
                fname_h5 = out_fname
                fname_other = in_fname
                format_other = in_format
            elif in_format == 'h5':
                self.converter = FROMH5[out_format](in_fname, out_fname)
                fname_h5 = in_fname
                fname_other = out_fname
                format_other = out_format
            else:
                raise ConversionError(
                    'Unknown conversion pair %s to %s!' % (in_format, out_format))
        except KeyError:
            raise ConversionError(
                'Unknown conversion pair %s to %s!' % (in_format, out_format))
        except Exception, e: # reformat all other exceptions to ConversionError
            raise ConversionError, ConversionError(str(e)), sys.exc_info()[2]

        try:
            if seperator:
                self.converter.set_seperator(seperator)

            self.converter.run()
            if verify:
                if format_other == 'uci':
                    raise ConversionError(
                        'Cannot verify UCI data format, %s!' % (fname_other))
                self.verify(fname_h5, fname_other, format_other)
        except Exception, e: # reformat all exceptions to ConversionError
            raise ConversionError, ConversionError(str(e)), sys.exc_info()[2]



    def is_binary(self, fname):
        """Return true if the given filename is binary.

        @param fname: filename to check if binary
        @type fname: string
        @return: if file is binary
        @rtype: boolean
        """
        f = open(fname, 'rb')
        try:
            CHUNKSIZE = 1024
            while 1:
                chunk = f.read(CHUNKSIZE)
                if '\0' in chunk: # found null byte
                    f.close()
                    return 1
                if len(chunk) < CHUNKSIZE:
                    break # done
        finally:
            f.close()

        return 0


    def get_filename(self, orig):
        """Convert a given filename to something that indicates HDF5.

        @param orig: original filename
        @type orig: string
        @return: HDF5-ified filename
        @rtype: string
        """
        return orig + '.h5'


    def get_fileformat(self, fname):
        """Determine fileformat by given filenname.

        @param fname: filename to get format from
        @type fname: string
        @return: format of given file(name)
        @rtype: string
        """
        suffix = fname.split('.')[-1]
        # just assume libsvm if no proper suffix
        if suffix.find('/') != -1:
            return 'libsvm'

        if suffix in ('txt', 'svm', 'libsvm'):
            return 'libsvm'
        elif suffix in ('arff'):
            return 'arff'
        elif suffix in ('h5', 'hdf5'):
            return 'h5'
        elif suffix in ('csv', 'tsv'):
            return 'csv'
        elif suffix in ('data'):
            return 'uci'
        elif suffix in ('bz2', 'gz', 'zip'):
            try:
                presuffix = fname.split('.')[-2]
                if presuffix == 'tar':
                    return presuffix + '.' + suffix
            except IndexError:
                pass
            return suffix
        elif suffix in ('mat', 'm'):
            return 'matlab'
        elif suffix in ('octave', 'oct'):
            return 'octave'
        else: # unknown
            return suffix


    def get_unparseable(self, fname):
        """Get data from unparseable files

        @param fname: filename to get data from
        @type fname: string
        @return: raw extract from unparseable file
        @rtype: dict with 'attribute' data
        """
        import tarfile, zipfile
        if zipfile.is_zipfile(fname):
            intro = 'ZIP archive'
            f = zipfile.ZipFile(fname)
            data = ', '.join(f.namelist())
            f.close()
        elif tarfile.is_tarfile(fname):
            intro = '(Zipped) TAR archive'
            f = tarfile.TarFile.open(fname)
            data = ', '.join(f.getnames())
            f.close()
        else:
            intro = 'Unparseable Data'
            if self.is_binary(fname):
                data = ''
            else:
                f = open(fname, 'r')
                i = 0
                data = []
                for l in f:
                    data.append(l)
                    i += 1
                    if i > base.NUM_EXTRACT:
                        break
                f.close()
                data = "\n".join(data)

        return {'data': [[intro, data]]}


    def get_extract(self, fname):
        """Get an extract of an HDF5 file.

        @param fname: filename to get get extract from
        @type fname: string
        @return: extract of an HDF5 file
        @rtype: dict with HDF5 attribute/dataset names as keys and their data as values
        """
        format = self.get_fileformat(fname)
        if format != 'h5':
            h5_fname = self.get_filename(fname)
            try:
                self.convert(fname, format, h5_fname, 'h5')
            except ConversionError:
                return self.get_unparseable(fname)
        else:
            h5_fname = fname

        extract = {
            'mldata': 0,
            'name': '',
            'comment': '',
            'names': [],
            'types': [],
            'data': [],
        }
        try:
            h5 = h5py.File(h5_fname, 'r')
        except h5py.h5e.LowLevelIOError:
            return extract

        attrs = ('mldata', 'name', 'comment')
        for a in attrs:
            if a in h5.attrs:
                extract[a] = h5.attrs[a]
        if 'data_descr/names' in h5:
            extract['names'] = h5['data_descr/names'][:].tolist()
        if 'data_descr/types' in h5:
            extract['types'] = h5['data_descr/types'][:].tolist()

        # only first NUM_EXTRACT items of attributes
        try:
            extract['data'] = []
            ne = base.NUM_EXTRACT

            if ('indptr' and 'indices') in h5['data']:
                # taking all data takes to long for quick viewing, but having just
                # this extract may result in less columns displayed than indicated
                # by attributes_names
                data = h5['data/data'][:h5['data/indptr'][ne+1]]
                indices = h5['data/indices'][:h5['data/indptr'][ne+1]]
                indptr = h5['data/indptr'][:ne+1]
                A=csc_matrix((data, indices, indptr)).todense().T
                extract['data'] = A[:ne].tolist()
            else:
                for dset in h5['data_descr/ordering']:
                    if dset == 'label': continue
                    dset = 'data/' + dset
                    if type(h5[dset][0]) == numpy.ndarray:
                        for i in xrange(len(h5[dset])):
                            extract['data'].append(h5[dset][i][:ne])
                    else:
                        extract['data'].append(h5[dset][:ne])
                extract['data'] = numpy.matrix(extract['data']).T

            # convert from numpy array to list, if necessary
            t = type(extract['data'][0])
            if t == numpy.ndarray or t == numpy.matrix:
                extract['data'] = [y for x in extract['data'] for y in x.tolist()]
        except KeyError:
            pass
        except ValueError:
            pass
        except IndexError:
            pass

        h5.close()
        return extract


    def get_num_instattr(self, fname):
        """Retrieve number of instances and number of attributes from given
        file.

        @param fname: filename to retrieve data from
        @type fname: string
        @return: number of instances and number of attributes
        @rtype: tuple containing 2 integers
        """
        h5 = h5py.File(fname, 'r')
        try:
            if 'indptr' in h5['data']: # sparse
                A = csc_matrix(
                    (h5['data']['data'], h5['data']['indices'], h5['data']['indptr'])
                )
                num_inst = A.shape[1]
                num_attr = A.shape[0]
            else:
                num_inst = 0
                num_attr = 0
                # this seems a bit non-intuitive aka magic...
                for name in h5['data_descr']['ordering']:
                    if name == 'label': continue
                    if len(h5['data'][name].shape) == 2:
                        num_attr += h5['data'][name].shape[0]
                        inst = h5['data'][name].shape[1]
                        if inst > num_inst:
                            num_inst = inst
                    else:
                        num_inst = h5['data'][name].shape[0]
                        num_attr += 1
        except:
            num_inst = -1
            num_attr = -1

        h5.close()
        return (num_inst, num_attr)


    def infer_seperator(self, fname):
        """Infer seperator for variables in given file.

        @param fname: filename to retrieve data from
        @type fname: string
        @return: inferred seperator
        @rtype: string
        """
        fp = open(fname, 'r')
        seperator = None
        minimum = 1

        for line in fp:
            num_splits = []
            for s in base.ALLOWED_SEPERATORS:
                l = len(line.split(s))
                if l > minimum:
                    minimum = l
                    seperator = s
            if seperator:
                break

        fp.close()
        if not seperator:
            return ''
        else:
            return seperator


    def _get_splitnames(self, fnames):
        """Helper function to get names of splits.

        Get a name like test_idx, train_idx from given filenames.

        @param fnames: filenames to get splitnames from
        @type fnames: list of string
        @return: names of splits
        @rtype: list of strings
        """
        names = []
        for name in fnames:
            n = name.split(os.sep)[-1]
            if n.find('train') != -1 or n.find('.tr') != -1:
                names.append('train_idx')
            elif n.find('.val') != -1:
                names.append('validation_idx')
            elif n.find('test') != -1 or n.find('.t') != -1 or n.find('.r') != -1:
                names.append('test_idx')
            else:
                names.append(0)

        # replace unknown name by test if train exists or train if test exists
        if 0 in names:
            if 'train_idx' in names:
                names[names.index(0)] = 'test_idx'
            elif 'test_idx' in names:
                names[names.index(0)] = 'train_idx'

        return names


    def _get_splitdata(self, fnames):
        """Get split data.

        @param fnames: filenames of related data files
        @type fnames: list of strings
        """
        names = self._get_splitnames(fnames)
        data = {}
        offset = 0
        for i in xrange(len(fnames)):
            count = sum(1 for line in open(fnames[i]))
            if names[i] in data: # in case we have multiple train/test idx
                data[names[i]].extend(range(offset, offset+count))
            else:
                data[names[i]] = range(offset, offset+count)
            offset += count

        return data


    def create_taskfile(self, name, fnames):
        """Create a Task file, using HDF5.

        @param name: name of the Task item
        @type name: string
        @param fnames: names of files to contain Task data
        @type fnames: list of strings
        @return: name of created Task file
        @rtype: string
        """
        fname = self.get_filename(name)
        h5 = h5py.File(fname, 'w')

        group = h5.create_group('/task')
        if self.converter and self.converter.labels_idx:
            group.create_dataset('label_dims', data=self.converter.labels_idx, compression=base.COMPRESSION)

        data = self._get_splitdata(fnames)
        for k,v in data.iteritems():
            if v:
                group.create_dataset(k, data=v, compression=base.COMPRESSION)

        h5.attrs['name'] = name
        h5.attrs['mldata'] = base.VERSION_MLDATA
        h5.attrs['comment'] = 'Task file'
        h5.close()

        return fname
