#!/usr/bin/python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sys
import re
import glob
import os
from subprocess import call
from optparse import OptionParser
import tempfile
import pdb

# Get the command line options parser
def get_cmd_param_parser():
  parser = OptionParser()
  parser.add_option("-d", "--process-dir", dest="data_dir",
      help="PATH containing IMB results files. This param is exclusive with -T.")
  parser.add_option("-n", "--fixed-nodes-num", dest="node_num",
      help="If the number of nodes during IMB run was fixed and scaling on PPN is desired then this is to be specified")

  parser.add_option("-p", "--fixed-ppn", dest="ppn",
      help="If the ppn during IMB run was fixed and scaling on Nnodes is desired then this is to be specified")

  parser.add_option("-T", "--tokens-list", dest="tokens_list",
      help="Comma separated list of the tokens of the following pattern IMB_RST_FILE#CollectiveName#Msgsize. This param is exclusive with '-d'.")

  parser.add_option("-s", "--save-to", dest="save_to", metavar="FILE",
      help="If this is specified then the result figure is written to the specified filename. Only applicable along with -T. If not specified the figure is shown in pop up window.")

  parser.add_option("-c", "--coll-include", dest="coll_include",
                    help="Comma separated list of collectives to be included into processing (Barrier,Bcast,Allgather,Allreduce,Alltoallv)")

  parser.add_option("-m", "--msgsize-include", dest="msgsize_include",
      help="Comma separated list of message sizes to be included into processing")

  parser.add_option("-f", "--files-include", dest="files_include",
      help="Comma separated list of file names to include into processing")

  parser.add_option("-x", "--files-exclude", dest="files_exclude",
      help="Comma separated list of file names to exclude from processing")

  parser.add_option("-b", "--benchmark", dest="benchmark",
      help="Benchmark which results are being parsed (imb,osu)")

  parser.add_option("-t", "--generate-tables", dest="generate_table",
      help="Adds table to summary.pdf")

  return parser


# Adds a new plot to the specified figure object
def add_graph(rst_colls,collname,msize,fig,filename,nodes_num,ppn, table_data = None):
    p = []
    t = []
    rst = []
    extra_label=""
    if not collname == "Barrier":
        if not msize in rst_colls[collname]:
            print "Msize ",msize, "is not found in rst for",collname
            return

        rst = rst_colls[collname][msize]
        extra_label = "[msize="+str(msize)+"]"
    else:
        rst = rst_colls[collname]

    rst = sorted(rst)
    for (procs,time) in rst:
        if nodes_num:
            p.append(procs/nodes_num)
        elif ppn:
            p.append(procs/ppn)
        else:
            p.append(procs)
        t.append(float(time))

    ax=fig.gca()

    markersize=8
    marker = 'o'
    if len(ax.get_lines()) > 6:
        marker = 's'
        markersize=5
    ax.plot(p,t,marker=marker,markersize=markersize,label=collname+extra_label+"["+os.path.basename(filename)+"]")

    if not table_data == None:
        if not fig in table_data:
            table_data[fig]={}
            table_data[fig]['header']=collname+extra_label
            table_data[fig]['xdata'] = p
            table_data[fig]['ydata'] = {}
            table_data[fig]['max'] = 0
        else:
            for pp in p:
                if not pp in table_data[fig]['xdata']:
                    table_data[fig]['xdata'].append(pp)

        table_data[fig]['ydata'][os.path.basename(filename)]=zip(p,t)
        if max(t) > table_data[fig]['max']:
            table_data[fig]['max'] = max(t)


# Parses a specified IMB result file
def get_line_imb(line, curr_coll):
    msize=None
    time = None

    if not curr_coll == 'Barrier':
        m = re.match('^\s+(\d+)\s+(\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s*$',line)
        if m:
            msize = int(m.group(1))
            time =  float(m.group(5))
    else:
        m = re.match('^\s+(\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s*$',line)
        if m:
            time = float(m.group(4))
            msize = -1
    return msize,time

def get_line_osu(line, curr_coll):
    msize=None
    time = None
    if not curr_coll == 'Barrier':
        m = re.match('^(\d+)\s+(\d+\.\d+)$',line)
        if m:
            msize = int(m.group(1))
            time =  float(m.group(2))
    else:
        m = re.match('^\s+(\d+\.\d+)$',line)
        if m:
            time = float(m.group(1))
            msize = -1
    return msize,time

def parse_file(filename,benchmark):
    print "Parsing ",filename
    rst_colls={}
    curr_coll=""
    curr_procs=0
    for line in open(filename).readlines():
        m = re.match('^benchrun_NP:\s(\d+)',line)
        if m:
            procs=int(m.group(1))
            # coll_result = rst_colls[curr_coll]
            # if not procs in coll_result:
                # coll_result[procs] = []
            curr_procs = procs

        if benchmark == "imb":
            m = re.match('^#\sBenchmarking\s(\w+)',line)
        else:
            m = re.match('^#\sOSU\sMPI\s(\w+)\s\w+\sTest',line)
        if m:
            coll=m.group(1)
            if not coll in rst_colls:
                if not coll == "Barrier":
                    rst_colls[coll] = {}
                else:
                    rst_colls[coll] = []
            curr_coll = coll


        if curr_coll == "":
            continue

        if benchmark == "imb":
            msize, time = get_line_imb(line, curr_coll)
        if benchmark == "osu":
            msize, time = get_line_osu(line, curr_coll)
        coll_result = rst_colls[curr_coll]
        if msize and time:
            if not msize == -1:
                if not msize in coll_result:
                    coll_result[msize] = [(curr_procs,time)]
                else:
                    coll_result[msize].append((curr_procs,time))
            else:
                coll_result.append((curr_procs,time))

    return rst_colls

def save_table(data, filename):
    f = tempfile.NamedTemporaryFile(delete=False)

    tab_header="{|l||"
    cells_header=[]
    cells_hnums="ppn"
    counter=1

    for key in data['ydata'].keys():
        tab_header += "l|"
        cells_header.append("#"+str(counter)+" -- "+key)
        cells_hnums += " & \\#" + str(counter)
        counter += 1
    tab_header += "}"

    numbers = []
    for ppn in data['xdata']:
        numbers.append(str(ppn))

    units = 'microsecs'
    divide_by = 1
    if float(data['max']) > float(10000.0):
        units = 'millisecs'
        divide_by = 1000.0

    for key,value in data['ydata'].iteritems():
        for i in range(len(data['xdata'])):
            p = data['xdata'][i]
            matches = [(x,y) for (x,y) in value if x == p]
            if matches:
                numbers[i] += " & %.2f" % (float(matches[0][1])/divide_by)
            else:
                numbers[i] += " & " + "---"

    f.write("""
\\documentclass[a4paper]{{article}}
\\usepackage[english]{{babel}}

\\begin{{document}}
{{\\Huge
\\begin{{verbatim}}
{0}
\\end{{verbatim}}
}}
{5}
\\begin{{verbatim}}
{1}
\\end{{verbatim}}
{{\\small
\\begin{{center}}
\\begin{{tabular}}{2}
\\hline \\hline
{3} \\\\
\\hline \\hline
{4}\\\\ \n
\\hline
\\end{{tabular}}
\\end{{center}}
}}
\\end{{document}}
""".format(filename,'\n'.join(cells_header),tab_header,cells_hnums,'\\\\ \n'.join(numbers)," units: "+units))
    f.flush()
    call(["pdflatex",f.name])
    call(["mv",os.path.basename(f.name+".pdf"),filename])
    print os.getcwd()
    call(["rm",os.path.basename(f.name)+".aux"])
    call(["rm",os.path.basename(f.name)+".log"])
    f.close()

def figs_sorter(x,y):
    x1 = x[0].split('#')
    y1 = y[0].split('#')
    if len(x1) < 2 or len(y1) < 2:
        return 1 if x1 < y1 else -1
    elif x1[0] == y1[0]:
        return int(x1[1]) - int(y1[1])
    else:
        return 1 if x1[0] < y1[0] else -1

def process_results(options):
    nodes_num = options.node_num
    data_dir = options.data_dir
    ppn = options.ppn
    args={}
    rst_colls = {}
    table_data={}

    if not data_dir:
        for arg in options.tokens_list.split(","):
            print "arg=",arg
            params = arg.split("#")
            assert(len(params))
            filename = params[0]
            if not os.path.exists(filename):
                print "Error: filename {0} does not exists. Check -F tokens.".format(filename)
                sys.exit(0)
            if not filename in args:
                args[filename] = []

            args[filename].append(params[1:])
            rst_colls[filename] = parse_file(filename,options.benchmark)
    else:
        files_include=[]
        if options.files_include:
            files_include = [os.path.basename(x) for x in options.files_include.split(',')]

        files_exclude=[]
        if options.files_exclude:
            files_exclude = [os.path.basename(x) for x in options.files_exclude.split(',')]

        for filename in glob.glob(os.path.join(data_dir,"*")):
            if (not files_include or os.path.basename(filename) in files_include ) and \
               not os.path.basename(filename) in files_exclude:
                rst_colls[filename] = parse_file(filename,options.benchmark)



    if not data_dir:
        fig = plt.figure()
        for filename, params in args.iteritems():
            for p in params:
                collname = p[0]
                msgsize = int(p[1]) if not len(p) < 2 else 0
                add_graph(rst_colls[filename],collname,msgsize,fig,filename,nodes_num,ppn)

        if nodes_num:
            fig.gca().set_xlabel('proc-per-node, nodes_num='+str(nodes_num))
        elif ppn:
            fig.gca().set_xlabel('# nodes, ppn='+str(ppn))
        else:
            fig.gca().set_xlabel('# processes')




        fig.gca().set_ylabel('t_avg, us')
        plt.grid()
        lgd = plt.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3, borderaxespad=-1)
        if not options.save_to:
            plt.show()
        else:
            plt.savefig(options.save_to, bbox_extra_artists=(lgd,), bbox_inches='tight')
    else:
        figs = {}

        for coll in ["Barrier", "Bcast", "Allgather", "Allreduce", "Alltoallv"]:
            if options.coll_include and not coll in options.coll_include:
                continue
            for filename, rst in rst_colls.iteritems():
                if coll in rst:
                    if not coll == "Barrier":
                        for msgsize in rst[coll]:
                            if options.msgsize_include and not msgsize in options.msgsize_include:
                                continue
                            id=coll+"#"+str(msgsize)
                            if not id in figs:
                                figs[id] = plt.figure()
                            add_graph(rst,coll,msgsize,figs[id],filename,nodes_num,ppn,table_data)
                    else:
                        id = coll
                        if not id in figs:
                            figs[id] = plt.figure()
                        add_graph(rst,coll,0,figs[id],filename,nodes_num,ppn,table_data)

        mergecmd = ["gs","-dBATCH","-dNOPAUSE","-q","-sDEVICE=pdfwrite","-sOutputFile=summary.pdf"]

        toc = open("pdfmarks","w")
        i = 0

        for id,fig in sorted(figs.iteritems(), cmp=figs_sorter):
            print "Writing ", id, " to pdf"
            i += 1
            if nodes_num:
                fig.gca().set_xlabel('proc-per-node, nodes_num='+str(nodes_num))
            elif ppn:
                fig.gca().set_xlabel('# nodes, ppn='+str(ppn))
            else:
                fig.gca().set_xlabel('# processes')

            fig.gca().set_ylabel('t_avg, us')
            fig.gca().grid()
            h,l = fig.gca().get_legend_handles_labels()
            # lgd =  fig.legend(h,l,bbox_to_anchor=(0., 1.02, 1., .102), loc=9, borderaxespad=1,prop={'size':8})
            lgd = fig.legend(h,l,loc=9,borderaxespad=1,prop={'size':8})
            fig.savefig(id+".pdf", bbox_extra_artists=(lgd,), bbox_inches='tight')
            mergecmd.append(id+".pdf")
            toc_id = i
            if options.generate_table:
                save_table(table_data[fig],id+"_table.pdf")
                mergecmd.append(id+"_table.pdf")
                toc_id = 2*i-1
            toc.write("[/Title ({0}) /Page {1} /OUT pdfmark\n".format(id,toc_id))


        toc.close()
        mergecmd.append("pdfmarks")
        call(mergecmd)
        for id in figs.keys():
            call(["rm",id+".pdf"])

def validate_params(options):
    if options.node_num:
        try:
            val = int(options.node_num)
            if val < 0:
                print "Error: Nodes number must be a positive value"
                sys.exit(0)
            options.node_num = val
        except ValueError:
            print "Error: Value provided for node number is incorrect"
            sys.exit(0)

    if options.ppn:
        try:
            val = int(options.ppn)
            if val < 0:
                print "Error: ppn number must be a positive value"
                sys.exit(0)
            options.ppn = val
        except ValueError:
            print "Error: Value provided for ppn number is incorrect"
            sys.exit(0)

    if options.data_dir:
        if not os.path.isdir(options.data_dir):
            print "Error: value provided for data_dir is incorrect"
            sys.exit(0)
        else:
            options.data_dir = os.path.abspath(options.data_dir)

    if options.data_dir and options.tokens_list:
        print "Error: params data_dir and tokens_list are mutually exclusive"
        sys.exit(0)

    if options.benchmark:
        if not options.benchmark == "imb" and not options.benchmark == "osu":
            print "Error: wrong benchmark param, should be either imb or osu"
            sys.exit(0)
    else:
        options.benchmark="imb"

    if options.coll_include:
        options.coll_include = options.coll_include.split(",")
        for coll in options.coll_include:
            if not coll in ["Barrier", "Bcast", "Allgather", "Allreduce", "Alltoallv"]:
                print "Error: incorrect name of coll '{0}' is specified in -c param".format(coll)
                sys.exit(0)

    if options.msgsize_include:
        options.msgsize_include = options.msgsize_include.split(",")
        msgs=[]
        for msgsize in options.msgsize_include:
            try:
                val = int(msgsize)
                if val < 0:
                    print "Error: msgsize specified with -m is less than 0"
                    sys.exit(0)
                else:
                    msgs.append(val)
            except ValueError:
                print "Error: incorrect msgsize '{0}' is specified in -m param".format(msgsize)
                sys.exit(0)
        options.msgsize_include = msgs

    if not options.data_dir and not options.tokens_list:
        print "Error: plz specify either data_dir or tokens_list"
        sys.exit(0)

def main():

    work_dir = os.getcwd()

    parser = get_cmd_param_parser()
    (options, args) = parser.parse_args()
    validate_params(options)
    process_results(options)

if __name__ == '__main__':
    main()
