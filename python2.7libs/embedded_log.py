"""
Copyright (c) <2021> <Oleh Bliznuk>

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgement in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
"""

import os, sys, threading, weakref, atexit
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *


class Outwrap (QObject):
    sig_outputWritten = Signal(object)

    def __init__(self ):
        QObject.__init__(self)
        self.stop = False
        self.redirectToStd = False 

    def Start(self,  n):


        if n == 1:
            self.streamObj =  sys.stdout
        else:
            self.streamObj = sys.stderr

        try:
            self.streamId = self.streamObj.fileno()
        except BaseException as e:
            self.streamId = self.streamObj.redir.fileno()  # maybe <win32com.axscript.client.framework.SafeOutput>  for  XSI  

        self.origStreamClone = os.dup(self.streamId)  # clone original fd
        self.mirrorPipe = os.pipe()  # return (r, w)
        os.dup2(self.mirrorPipe[1],  self.streamId)  # (fd,fd2) duplicate file descriptor fd to fd2 
        os.close(self.mirrorPipe[1])  # close write counterpart as we dont need it

        self.workerThread = threading.Thread(target=self.Process)
        self.workerThread.daemon = True  # thread will term on app exit
        self.workerThread.start()

    def Process(self):
        while True:
            data = os.read(self .mirrorPipe [0], 1024)
            if (not data 
            #or data .find(b"\b") > -1
            )  and  self .stop is True:
                os.dup2(self.origStreamClone, self.streamId)
                self.sig_outputWritten = None
                break
            self .sig_outputWritten .emit(data)
            if self.redirectToStd :
                os.write( self .origStreamClone ,data )
        os.write(self.streamId, ( "# redirected stream closed successfully, id:" + str(self.origStreamClone) + "\n").encode("utf8"))

    def __del__(self):
        self.stop = True
        
coutWrap = Outwrap()
cerrWrap = Outwrap()

"""
def CloseWraps():
    coutWrap.stop = True
    cerrWrap.stop = True
    sys.stdout.write("\b")
    sys.stderr.write("\b")
    coutWrap.workerThread .join()
    cerrWrap.workerThread .join()

#QApplication().aboutToQuit.connect(CloseWraps) # signal is never emitted in houdini by unknown reasons 
atexit.register(CloseWraps)
"""

coutWrap.Start(1)
cerrWrap.Start(2)


class HLighter ( QSyntaxHighlighter) :

    def fm(color, style=''):
        _color = QColor()
        _color.setNamedColor(color)
        _format = QTextCharFormat()
        _format.setForeground(_color)
        if 'bold' in style:
            _format.setFontWeight(QFont.Bold)
        if 'italic' in style:
            _format.setFontItalic(True)
        return _format

    styles = {
        'warning': fm('orange'),
        'error': fm('red'),
        'info': fm('green'),
    }

    kw_error  = ['error',  'fatal', 'critical', 'abort']
    kw_warning =  [  'warn', 'warning' ]
    kw_info = ['info', 'verb', 'verbose']

    def __init__(self, ted_parent ):
        super(HLighter, self) .__init__(ted_parent)
        rules = []
        rules += [(r'%s' % w, 0, HLighter.styles['error'])  for w in HLighter.kw_error]
        rules += [(r'%s' % w, 0, HLighter.styles['warning']) for w in HLighter.kw_warning]
        rules += [(r'%s' % w, 0, HLighter.styles['info']) for w in HLighter.kw_info]
        self.rules = [(QRegExp(pat), index, fmt)   for (pat, index, fmt) in rules]

    def highlightBlock(self, text):
        for expression, nth, format in self.rules:
            index = expression.indexIn(text, 0)
            while index >= 0:
                index = expression.pos(nth)
                l =  len(expression.cap(nth) )
                self.setFormat(index, l, format)
                index = expression.indexIn(text, index + l)
        self.setCurrentBlockState(0)




class EmbeddedLogWindow(QWidget):
    def __init__(self,parent=None):
        super(EmbeddedLogWindow, self).__init__(parent)
        self.ted = QPlainTextEdit ()
        self.pbtn_clear = QPushButton ("Clear") ; self.pbtn_clear .setFixedWidth(80)
        self.chbx_wrapwords = QCheckBox ("Wrap Words") ; self.chbx_wrapwords.setChecked(True)
        self.lbl_maxln = QLabel ("Max lines: ")
        self.spbx_maxln = QSpinBox () ;self.spbx_maxln .setMaximum(999999999) ; self.spbx_maxln .setValue(500) ; self.spbx_maxln.setFixedWidth(60)
        self.chbx_redirect = QCheckBox ("Redirect to console") ; self.chbx_wrapwords.setChecked(False)

        lay_root = QVBoxLayout ()
        lay_root .addWidget(self.ted)

        lay_ctrl = QHBoxLayout ()
        lay_ctrl .addWidget(self.pbtn_clear )
        lay_ctrl.addWidget(self.lbl_maxln)
        lay_ctrl .addWidget( self.spbx_maxln )
        lay_ctrl .addWidget(self.chbx_wrapwords)
        lay_ctrl .addWidget( self.chbx_redirect )
        lay_ctrl .addStretch(1)

        lay_root .addLayout(lay_ctrl )
        self .setLayout(lay_root)

        self.hl = HLighter (self.ted.document())

        global coutWrap
        global cerrWrap
        coutWrap.sig_outputWritten.connect(self.HandleOutput)
        cerrWrap.sig_outputWritten.connect(self.HandleOutput)

        self.chbx_wrapwords.stateChanged .connect (self.OnCtrlChange )
        self.pbtn_clear .released .connect ( lambda : self .ted.clear() )
        self.spbx_maxln .valueChanged .connect ( self. OnCtrlChange )
        self.chbx_redirect .stateChanged .connect( self.OnRedirChange  )
        self.OnCtrlChange()

    def HandleOutput(self, text):
        self.ted.moveCursor(QTextCursor.End)
        self.ted.insertPlainText(text.decode ("utf8"))

    def OnCtrlChange (self ):
        self. ted .setLineWrapMode( QPlainTextEdit .LineWrapMode.WidgetWidth if self.chbx_wrapwords .isChecked() else  QPlainTextEdit .LineWrapMode.NoWrap )
        self.ted .setMaximumBlockCount  ( self.spbx_maxln .value() )

    def OnRedirChange (self ) :
        coutWrap.redirectToStd = self.chbx_redirect.checkState()
        cerrWrap.redirectToStd = self.chbx_redirect.checkState()

        
 
