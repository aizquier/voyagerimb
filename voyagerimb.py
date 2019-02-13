"""
** voyagerimb.py - A browser for the NASA's Voyager Golden Disk images **

Copyright (c) <2017> Manuel Arturo Izquierdo <aizquier@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys
import os
import subprocess
import numpy as np
import scipy.io.wavfile
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import tkinter as tk
from PIL import Image

# * support for previous matplotlib versions (v1, v2) and the current v3
mpltlib3 = True if int(matplotlib.__version__.split('.')[0]) > 2 else False
if mpltlib3:
    from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg, NavigationToolbar2Tk
        )
    from tkinter import messagebox, filedialog
else:
    from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg, NavigationToolbar2TkAgg
    )
    from tkinter import messagebox


class ValidatedEntry(object):
    def __init__(self, *args, **kwargs):
        self.textvariable = tk.StringVar()
        kwargs['textvariable'] = self.textvariable

        self.Entry = tk.Entry(*args, **kwargs)


class NumericalIntEntry(ValidatedEntry):
    def textvariable_as_int(self):
        try:
            return int(self.textvariable.get())
        except ValueError:
            print("Error: non numeric (int) value in entry!")
            return None


class NumericalFloatEntry(ValidatedEntry):
    def textvariable_as_float(self):
        try:
            return float(self.textvariable.get())
        except ValueError:
            print("Error: non numeric (float) value in entry!")
            return None


class FileMenu(object):
    def openfile(self):
        filename = tk.filedialog.askopenfilename(
            initialdir=os.getcwd(),
            title="Select file",
            filetypes=(("wav files", "*.wav"), )
        )

        if len(filename) != 0:
            try:
                self.browser.model_load_audio_data(filename)
            except:
                print("Invalid wav file")
                return
            self.browser.imager.view_plot_image()

    def sync_invert_signal(self, *args):
        self.browser.invert_signal = self.invert_signal.get()
        self.browser.imager.view_plot_image()

    def sync_flip_horizontal(self, *args):
        self.browser.flip_horizontal = self.flip_horizontal.get()
        self.browser.imager.view_plot_image()

    def model_init(self):
        self.invert_signal = tk.BooleanVar()
        self.invert_signal.set(False)
        self.invert_signal.trace("w", self.sync_invert_signal)

        self.flip_horizontal = tk.BooleanVar()
        self.flip_horizontal.set(False)
        self.flip_horizontal.trace("w", self.sync_flip_horizontal)

    def __save_image(self, resize=False):
        filename = tk.filedialog.asksaveasfilename(defaultextension=".bin")
        if filename is None:# asksaveasfile return `None` if dialog closed with "cancel".
            return

        data = np.array(self.browser.imager.model_get_segment())
        x1, x2 = np.min(data), np.max(data)
        y1, y2 = 0, 255.0
        m = (y2 - y1) / (x2 - x1)
        b = y2 - (m * x2)
        data_rescaled_colors = ((m * data) + b).astype(np.uint8)
        image = Image.fromarray(data_rescaled_colors)
        if resize:
            image = image.resize((image.width, int(image.width * (4.0 / 3.0)) ))

        try:
            image.save(filename)
        except KeyError:
            messagebox.showerror("Export image", "Invalid image format.\nTry \
                using file extensions like .png or .jpg")
            return
        except IOError:
            messagebox.showerror("Export image",
                                 "Error saving image.\nCheck that you have \
                                 enough disk space\nor right privileges")
            return

        messagebox.showinfo(
            "Export image", "Image exported as %s" % (filename)
            )

    def save_image_raw_size(self):
        self.__save_image(resize=False)

    def save_image_resized(self):
        self.__save_image(resize=True)

    def about(self):
        '''Starts project webpage in the default system's web browser'''

        webpage = "https://github.com/aizquier/voyagerimb"

        # * MacOS
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', webpage))
        # * Windows
        elif os.name == 'nt':
            os.startfile(webpage)
        # * Linux
        elif os.name == 'posix':
            subprocess.Popen(['xdg-open', webpage])

    def __init__(self, parent):
        self.browser = parent
        self.model_init()
        menubar = tk.Menu(parent.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open WAV...", command=self.openfile)
        filemenu.add_separator()
        filemenu.add_command(
                label="Export image...",
                command=self.save_image_resized)
        filemenu.add_command(
                label="Export image (raw size)...",
                command=self.save_image_raw_size)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=parent.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_checkbutton(
                label="Invert audio signal",
                onvalue=True, offvalue=False,
                variable=self.invert_signal)
        filemenu.add_checkbutton(
                label="Flip horizontal",
                onvalue=True,
                offvalue=False,
                variable=self.flip_horizontal)
        menubar.add_cascade(label="Image", menu=filemenu)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="About...", command=self.about)
        menubar.add_cascade(label="Help", menu=filemenu)

        parent.root.config(menu=menubar)


class Imager(object):

    def model_init(self):
        self.first = True
        pass

    def model_get_segment(self):
        offset = self.browser.offset
        scan_width = self.browser.scan_line_width
        image_data = []
        offset_exceeded = False

        for scan in range(self.browser.number_of_scans):
            chunk = [-_m if self.browser.invert_signal
                     else _m for _m in
                     self.browser.audio_data[int(offset):int(offset) + scan_width]]
            if len(chunk) != scan_width:
                chunk = np.zeros(scan_width)
                offset_exceeded = True
            image_data.append(chunk)
            offset += scan_width + self.browser.adjust

        if offset_exceeded:
            self.browser.offset_exceeded = True
        else:
            self.browser.offset_exceeded = False

        return image_data

    def view_plot_image(self):
        if self.browser.audio_data is None:
            if self.first:
                self.first = False
            else:
                self.browser.view_nodata_error()
            return

        self.browser.root.config(cursor="watch")
        self.browser.root.update()
        image_data = self.model_get_segment()

        if not self.browser.offset_exceeded:
            self.ax1.clear()
            self.ax2.clear()
            self.ax1.set_xlim([self.browser.scan_line_width, 0]
                              if self.browser.flip_horizontal else [0, self.browser.scan_line_width])
            self.ax1.set_ylim([self.browser.number_of_scans, 0])
            self.ax1.imshow(image_data, aspect='auto', cmap='gray')
            self.ax1.plot([0, self.browser.scan_line_width], [self.browser.plot_scanline, self.browser.plot_scanline])

            self.ax2.set_xlim([self.browser.scan_line_width, 0]
                              if self.browser.flip_horizontal else [0, self.browser.scan_line_width])
            self.ax2.set_ylim([-0.5, 0.5])
            self.ax2.set_xlabel("Offset (relative)")
            self.ax2.set_ylabel("signal")
            self.ax2.plot(range(len(image_data[self.browser.plot_scanline])), image_data[self.browser.plot_scanline])
            if self.mpltlib3:
                self.canvas.draw()
            else:
                self.canvas.show()
        else:
            self.browser.view_offset_exceeded_error()

        self.browser.root.config(cursor="")

    def view_init(self):
        self.frame = tk.LabelFrame(self.browser.workframe, text=" Image ")
        self.frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=7, pady=7)
        self.figure = plt.figure(figsize=(8, 12), dpi=70)
        self.ax1 = plt.subplot2grid((50,40), (0, 0), rowspan=40, colspan=40)
        self.ax2 = plt.subplot2grid((50,40), (42, 0), rowspan=8, colspan=40, sharex=self.ax1)
        plt.subplots_adjust(left=0.1, bottom=0.05, right=0.95, top=0.97, wspace=0.2, hspace=0.2)
        self.view_plot_image()
        self.canvas = FigureCanvasTkAgg(self.figure, self.frame)

        if self.mpltlib3:
            self.canvas.draw()
            toolbar = NavigationToolbar2Tk(self.canvas, self.frame).update()
        else:
            self.canvas.show()
            toolbar = NavigationToolbar2TkAgg(self.canvas, self.frame).update()

        self.canvas.get_tk_widget().pack(
            side=tk.BOTTOM,
            fill=tk.BOTH,
            expand=True)

        self.canvas._tkcanvas.pack(
            side=tk.TOP,
            fill=tk.BOTH,
            padx=2,
            pady=2,
            expand=True)
        self.frame.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
            padx=7,
            pady=7)

    def __init__(self, parent, mpltlib3=True):
        self.mpltlib3 = mpltlib3
        self.browser = parent
        self.model_init()
        self.view_init()



class OffsetControl(object):
        def model_modify_offset(self, sign):
            if self.browser.audio_data is not None:
                maxsize = len(self.browser.audio_data) - 1

                textvariable = self.offset_entry.textvariable_as_int()
                if textvariable is None:
                    return

                if textvariable == self.browser.offset:
                    delta = {
                        "1"         : 1,
                        "10"        : 10,
                        "100"       : 100,
                        "1000"      : 1000,
                        "NoS x SLW" : self.browser.number_of_scans * self.browser.scan_line_width,
                        "100 x SLW" : 100 * self.browser.scan_line_width,
                        "10 x SLW"  : 10 *self.browser.scan_line_width,
                        "1 x SLW"   : self.browser.scan_line_width
                    }[self.interval_value_variable.get()]

                    if sign == "+":
                        self.browser.offset += delta
                    else:
                        self.browser.offset -= delta
                        None

                    self.offset_entry.textvariable.set(self.browser.offset)
                else:
                    self.browser.offset = int(self.offset_entry.textvariable.get())
                    None

                if self.browser.offset < 0:
                    self.browser.offset = 0
                    self.offset_entry.textvariable.set(0)

                if self.browser.offset > maxsize:
                    self.browser.offset = maxsize
                    self.offset_entry.textvariable.set(maxsize)

                self.browser.imager.view_plot_image()

            else:
                self.browser.view_nodata_error()

        def model_increment_offset(self):
            self.model_modify_offset("+")

        def model_decrement_offset(self):
            self.model_modify_offset("-")

        def model_sync_with_entry(self, *args):
            if self.browser.audio_data is not None:
                textvariable_as_int = self.offset_entry.textvariable_as_int()
                if textvariable_as_int is None:
                    return

                maxsize = len(self.browser.audio_data) - 1
                if textvariable_as_int < 0:
                    self.browser.offset = 0
                    self.offset_entry.textvariable.set("0")
                elif textvariable_as_int > maxsize:
                    self.browser.offset = maxsize
                    self.offset_entry.textvariable.set(str(maxsize))
                else:
                    self.browser.offset = textvariable_as_int
            else:
                print("No audio data in memory!!")

        def model_init(self):
            self.interval_value_variable = tk.StringVar()
            self.interval_value_variable.set(1000)

        def view_init(self):
            self.frame = tk.LabelFrame(self.controlwidgets.frame, text=" Offset ")
            ftop = tk.Frame(self.frame)
            fbottom = tk.Frame(self.frame)

            self.offset_entry = NumericalIntEntry(ftop)
            self.offset_entry.textvariable.set("0")
            self.offset_entry.textvariable.trace("w", self.model_sync_with_entry)
            self.offset_entry.Entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Button(ftop, text="sub", width=1, command=self.model_decrement_offset).pack(side=tk.LEFT)
            tk.Button(ftop, text="add", width=1, command=self.model_increment_offset).pack(side=tk.LEFT)

            _mm = tk.Frame(fbottom)

            for radiobutrow in [["1000", "100", "10", "1"], ["NoS x SLW", "100 x SLW", "10 x SLW", "1 x SLW"]]:
                _mmm = tk.Frame(_mm)
                for interval_value in radiobutrow:
                    _m = tk.Radiobutton(_mmm,
                        text="%s" % (interval_value),
                        indicatoron=0,
                        foreground="#940015",
                        variable=self.interval_value_variable,
                        value=interval_value,
                        width=1
                    )
                    _m.pack(side=tk.TOP, fill=tk.X, expand=True)
                _mmm.pack(side=tk.LEFT, fill=tk.X, expand=True)
                None

            _mm.pack(side=tk.BOTTOM, fill=tk.X, expand=True)

            ftop.pack(side=tk.TOP, fill=tk.BOTH,  padx=4, pady=4, expand=True)
            fbottom.pack(side=tk.TOP, fill=tk.BOTH,  padx=4, pady=4, expand=True)
            self.frame.pack(side=tk.TOP, fill=tk.X, padx=7, pady=7, expand=False)

        def __init__(self, parent):
            self.controlwidgets = parent
            self.browser = parent.browser
            self.model_init()
            self.view_init()


class ScanLineWidthControl(object):

    def model_increase(self):
        newvalue = self.scan_line_width_entry.textvariable_as_int() + 1
        self.scan_line_width_entry.textvariable.set(str(newvalue))

    def model_decrease(self):
        newvalue = self.scan_line_width_entry.textvariable_as_int() - 1
        self.scan_line_width_entry.textvariable.set(str(newvalue))

    def model_sync_with_entry(self, *args):
        if self.browser.audio_data is not None:
            textvariable_as_int = self.scan_line_width_entry.textvariable_as_int()
            if textvariable_as_int is None:
                return
            if textvariable_as_int < 0:
                self.browser.scan_line_width = 0
                self.scan_line_width_entry.textvariable.set(0)
            else:
               self.browser.scan_line_width = textvariable_as_int

    def __init__(self, parent):
        self.parent = parent
        self.browser = parent.browser
        self.frame = tk.LabelFrame(self.parent.frame, text=" Scan line width (SLW)")
        self.scan_line_width_entry = NumericalIntEntry(self.frame)
        self.scan_line_width_entry.textvariable.set(3197)
        self.scan_line_width_entry.textvariable.trace("w", self.model_sync_with_entry)
        self.scan_line_width_entry.Entry.pack(side=tk.LEFT, fill=tk.X, padx=4, pady=4, expand=True)
        tk.Button(self.frame, text="-", command=self.model_decrease).pack(side=tk.LEFT)
        tk.Button(self.frame, text="+", command=self.model_increase).pack(side=tk.LEFT)
        self.frame.pack(side=tk.TOP, fill=tk.X, padx=7, pady=7, expand=False)


class NumberOfScansControl(object):

    def model_increase(self):
        newvalue = self.number_of_scans_entry.textvariable_as_int() + 1
        self.number_of_scans_entry.textvariable.set(str(newvalue))

    def model_decrease(self):
        newvalue = self.number_of_scans_entry.textvariable_as_int() - 1
        self.number_of_scans_entry.textvariable.set(str(newvalue))

    def model_sync_with_entry(self, *args):
        if self.browser.audio_data is not None:
            textvariable_as_int = self.number_of_scans_entry.textvariable_as_int()
            if textvariable_as_int is None:
                return
            if textvariable_as_int < 0:
                self.browser.number_of_scans = 0
                self.number_of_scans_entry.textvariable.set(0)
            else:
                self.browser.number_of_scans = textvariable_as_int

    def __init__(self, parent):
        self.parent = parent
        self.browser = parent.browser
        self.frame = tk.LabelFrame(
            self.parent.frame,
            text=" Number of scans (NoS) per image ")
        self.number_of_scans_entry = NumericalIntEntry(self.frame)
        self.number_of_scans_entry.textvariable.set(512)
        self.number_of_scans_entry.textvariable.trace(
            "w", self.model_sync_with_entry)
        self.number_of_scans_entry.Entry.pack(
            side=tk.LEFT, fill=tk.X, padx=4, pady=4, expand=True)
        tk.Button(self.frame, text="-", command=self.model_decrease).pack(
            side=tk.LEFT)
        tk.Button(self.frame, text="+", command=self.model_increase).pack(
            side=tk.LEFT)
        self.frame.pack(side=tk.TOP, fill=tk.X, padx=7, pady=7, expand=False)


class AdjustControl(object):
    def model_increase(self):
        newvalue = self.adjust_control_entry.textvariable_as_float() + 0.01
        self.adjust_control_entry.textvariable.set("%2.3f" % (newvalue))

    def model_decrease(self):
        newvalue = self.adjust_control_entry.textvariable_as_float() - 0.01
        self.adjust_control_entry.textvariable.set("%2.3f" % (newvalue))

    def model_sync_with_entry(self, *args):
        if self.browser.audio_data is not None:
            textvariable_as_float = self.adjust_control_entry.textvariable_as_float()
            if textvariable_as_float is None:
                return
            self.browser.adjust = textvariable_as_float

    def __init__(self, parent):
        self.parent = parent
        self.browser = parent.browser
        self.frame = tk.LabelFrame(self.parent.frame, text=" Offset Adjust ")
        self.adjust_control_entry = NumericalFloatEntry(self.frame)
        self.adjust_control_entry.textvariable.set(0)
        self.adjust_control_entry.textvariable.trace(
            "w",
            self.model_sync_with_entry)
        self.adjust_control_entry.Entry.pack(
            side=tk.LEFT,
            fill=tk.X,
            padx=4,
            pady=4,
            expand=True)
        tk.Button(self.frame, text="-", command=self.model_decrease).pack(
            side=tk.LEFT)
        tk.Button(self.frame, text="+", command=self.model_increase).pack(
            side=tk.LEFT)
        self.frame.pack(side=tk.TOP, fill=tk.X, padx=7, pady=7, expand=False)


class ScanlinePlotSliderControl(object):

    def model_increase(self):
        self.scale.set(self.scale.get() + 1)

    def model_decrease(self):
        self.scale.set(self.scale.get() - 1)

    def model_sync_with_entry(self, v):
        self.browser.plot_scanline = int(v)

    def model_slide_range_update(self, *args):
        newmax = self.parent.numberofscans.number_of_scans_entry.textvariable_as_int()
        if self.browser.plot_scanline > newmax:
            self.browser.plot_scanline = newmax
        self.scale.configure(to=newmax)

    def __init__(self, parent):
        self.parent = parent
        self.browser = parent.browser
        self.frame = tk.LabelFrame(self.parent.frame, text=" Plot scanline ")
        self.scale = tk.Scale(
            self.frame,
            from_=0,
            to=self.browser.number_of_scans,
            orient=tk.HORIZONTAL,
            showvalue=True,
            command=self.model_sync_with_entry )
        self.scale.pack(
            side=tk.LEFT,
            fill=tk.X,
            padx=4,
            pady=4,
            anchor=tk.CENTER,
            expand=True)
        self.parent.numberofscans.number_of_scans_entry.textvariable.trace(
            "w",
            self.model_slide_range_update)
        tk.Button(self.frame, text="-", command=self.model_decrease).pack(
            side=tk.LEFT)
        tk.Button(self.frame, text="+", command=self.model_increase).pack(
            side=tk.LEFT)
        self.frame.pack(side=tk.TOP, fill=tk.X, padx=7, pady=7, expand=False)


class ControlWidgets(object):

    def __init__(self, parent):
        self.browser = parent
        self.frame = tk.Frame(self.browser.workframe)
        self.scansize = ScanLineWidthControl(self)
        self.numberofscans = NumberOfScansControl(self)
        self.adjust = AdjustControl(self)
        self.scanlineplot = ScanlinePlotSliderControl(self)
        self.offset = OffsetControl(self)
        self.plotbutton = tk.Button(
            self.frame,
            text="REPLOT",
            height=3,
            command=self.browser.imager.view_plot_image,
            relief=tk.GROOVE,
            borderwidth=4)
        self.plotbutton.pack(
            side=tk.TOP,
            fill=tk.X,
            padx=4,
            pady=4,
            expand=False)
        self.frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)


class VoyagerBrowser(object):

    def model_load_audio_data(self, filename):
        self.root.config(cursor="watch")
        self.root.update()
        self.rate, self.audio_data = scipy.io.wavfile.read(filename)
        self.root.config(cursor="")

    def model_init(self):
        self.audio_data = None
        self.offset = 0
        self.scan_line_width = 3197
        self.number_of_scans = 512
        self.adjust = 0
        self.plot_scanline = 0
        self.invert_signal = False
        self.flip_horizontal = False
        self.offset_exceeded = False

    def on_close(self):
        print("Bye!")
        self.root.destroy()
        sys.exit(0)

    def view_init(self, mpltlib3):
        self.root = tk.Tk()
        self.workframe = tk.Frame(self.root)
        self.menu = FileMenu(self)
        self.imager = Imager(self, mpltlib3)
        self.controlwidgets = ControlWidgets(self)
        self.workframe.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.title("Voyager Audio Image Browser")

    def view_nodata_error(self):
        print("No data in memory to plot yet!!")
        messagebox.showerror("Error", "No data in memory to plot yet!!")

    def view_offset_exceeded_error(self):
        print("Cannot plot. End of data!!")
        messagebox.showerror("Error", "Cannot plot. End of data!!")

    def view_mainloop(self):
        self.root.mainloop()

    def __init__(self, mpltlib3=True):
        self.model_init()
        self.view_init(mpltlib3)
        self.view_mainloop()


if __name__ == "__main__":
    VoyagerBrowser(mpltlib3)
