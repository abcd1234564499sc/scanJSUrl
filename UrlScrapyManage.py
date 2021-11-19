#!/usr/bin/env python
# coding=utf-8
import json
import re
import urllib.parse
from queue import Queue

from PyQt5.QtCore import QThread, pyqtSignal
from bs4 import BeautifulSoup

import myUtils


class UrlScrapyManage(QThread):
    signal_result = pyqtSignal(str)
    signal_log = pyqtSignal([str], [str, str])
    signal_progress = pyqtSignal(str, str)
    signal_end = pyqtSignal()

    def __init__(self, scrawlUrl="", parent=None):
        super(UrlScrapyManage, self).__init__(parent)
        self.scrawlUrl = scrawlUrl
        self.vistedLinkList = []
        self.urlQueue = Queue()
        self.processCount = 5
        self.resultList = []

    def run(self):
        self.signal_log.emit("开始扫描")
        self.vistedLinkList.append(self.scrawlUrl)
        self.urlQueue.put(self.scrawlUrl)
        visitCount = 0
        while not self.urlQueue.empty():
            nowUrl = self.urlQueue.get()
            visitCount = visitCount + 1
            remainCount = self.urlQueue.qsize()
            self.signal_progress.emit(str(visitCount),str(remainCount))
            self.scrapyProcess(nowUrl)
        self.signal_log.emit("扫描结束")
        self.signal_end.emit()

    # 访问并分析URL，生成多个能正常访问的结果字典并写入结果队列
    # 字典结构为：{"url":"访问地址","status":"响应码","title":"标题"}
    def scrapyProcess(self, url):
        reDic = {}

        # 获得后缀
        urlSuffix = myUtils.getUrlFileSuffix(url)

        # 请求这个URL
        self.signal_log.emit("请求地址：" + url)
        try:
            tempDic = myUtils.requestsUrl(url)
        except Exception as ex:
            self.signal_log.emit(str(ex),color="red")

        if tempDic["checkFlag"]:
            # 访问成功
            status = tempDic["status"]
            title = tempDic["title"]
            content = tempDic["pageContent"]
            if urlSuffix == "js":
                # 是js文件，使用js文件分析方法分析
                reLinkList = self.analysisJSPage(myUtils.getUrlDomain(self.scrawlUrl), url, content)
                # 写入新的链接
                for tempLink in reLinkList:
                    if tempLink not in self.vistedLinkList:
                        self.vistedLinkList.append(tempLink)
                        self.urlQueue.put(tempLink)
                    else:
                        pass
            else:  # if urlSuffix == "js":
                # 不是js文件，按HTML文件分析方法分析
                reHtmlDic = self.analysisHtmlPage(pageUrl=tempDic["url"], pageContent=content)
                reAList = reHtmlDic["a"]
                reJsList = reHtmlDic["js"]
                # 写入新的链接
                for tempLink in reAList:
                    if tempLink not in self.vistedLinkList:
                        self.vistedLinkList.append(tempLink)
                        self.urlQueue.put(tempLink)
                    else:
                        pass
                for tempLink in reJsList:
                    if tempLink not in self.vistedLinkList:
                        self.vistedLinkList.append(tempLink)
                        self.urlQueue.put(tempLink)
                    else:
                        pass
            # 构建返回结果
            reDic["url"] = url
            reDic["status"] = status
            reDic["title"] = title
            reDicStr = json.dumps(reDic)
            self.signal_result.emit(reDicStr)
            self.resultList.append(reDic)
        else:  # if reDic["checkFlag"]
            pass

    # 分析一个Html页面，返回其中的链接以及引用的js链接，
    # 返回一个字典，字典结构为：{"a":[a标签的链接数组],"js":[js链接数组]}
    def analysisHtmlPage(self, pageUrl="", pageContent=""):
        reDic = {}
        aLinkList = []
        jsLinkList = []

        # 获得当前URL的域名值
        nowDomain = myUtils.getUrlDomain(pageUrl)

        # 解析当前页面
        soup = BeautifulSoup(pageContent, "lxml")
        # 获取所有a标签
        aList = soup.find_all("a")
        for aItem in aList:
            if "href" in aItem.attrs.keys():
                # 获取链接
                nowHref = aItem.attrs["href"]
                nowHref = urllib.parse.urljoin(pageUrl, nowHref)
                # 判断是否属于爬取域名的子域名
                if myUtils.ifSameMainDomain(nowDomain, myUtils.getUrlDomain(nowHref)):
                    aLinkList.append(nowHref)
        # 获取所有js链接
        scriptList = soup.find_all("script")
        for scriptItem in scriptList:
            if "src" in scriptItem.attrs.keys():
                # 获取链接
                nowSrc = scriptItem.attrs["src"]
                nowSrc = urllib.parse.urljoin(pageUrl, nowSrc)
                # 判断是否是js链接且属于爬取域名的子域名
                if urllib.parse.urlparse(nowSrc)[2].split(".")[-1] == "js" and myUtils.ifSameMainDomain(nowDomain,
                                                                                                        myUtils.getUrlDomain(
                                                                                                            nowSrc)):
                    jsLinkList.append(nowSrc)
        # 结果去重
        aLinkList = list(set(aLinkList))
        jsLinkList = list(set(jsLinkList))

        # 构造返回字典
        reDic["a"] = aLinkList
        reDic["js"] = jsLinkList
        return reDic

    # 分析js文件，传入一个网站域名，当前js文件地址，以及js文件的源码，返回一个链接列表
    def analysisJSPage(self, nowDomain="", nowUrl="", pageContent=""):
        reList = []
        pattern = re.compile(r'(?:(?:http|https)://|["|\[|\']/).*?["|\]|\']', flags=re.I)
        startPattern = re.compile(r'^["|\'|[]', flags=re.I)
        endPattern = re.compile(r'["|\'|}]$', flags=re.I)
        httpPattern = re.compile(r'(?:http|https)://', flags=re.I)

        nowUrlDomain = myUtils.getUrlDomain(nowUrl)
        # 提取所有符合URL格式的字符串
        reResults = pattern.findall(pageContent)
        for link in reResults:
            # 替换开始的引号
            link = startPattern.sub("", link)
            # 替换结束的引号
            link = endPattern.sub("", link)
            if httpPattern.match(link):
                # 链接自带协议，是完整的地址
                # 判断是否属于爬取域名的子域名
                if myUtils.ifSameMainDomain(nowDomain, myUtils.getUrlDomain(link)):
                    reList.append(link)
            else:
                # 与网站域名结合
                reList.append(urllib.parse.urljoin(nowDomain, link))
                # 与输入网址相结合
                reList.append(urllib.parse.urljoin(self.scrawlUrl, link))
                # 与js文件域名结合
                reList.append(urllib.parse.urljoin(nowUrlDomain, link))
                # 与js文件地址结合
                reList.append(urllib.parse.urljoin(nowUrl, link))

        # 去重
        reList = list(set(reList))
        return reList
