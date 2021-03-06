#!/usr/bin/env python
# -*- coding: utf-8 -*-

############Stackoverflow Indexing Code############

import sys

sys.path.append("/Libs/jsoup-1.8.2.jar")
sys.path.append("/Libs/lucene-analyzers-common-4.10.4.jar")
sys.path.append("/Libs/lucene-core-4.10.4.jar")
sys.path.append("/Libs/lucene-queries-4.10.4.jar")
sys.path.append("/Libs/lucene-queryparser-4.10.4.jar")
sys.path.append("/Libs/jython-standalone-2.7.0.jar")
sys.path.append("/Libs/mysql-connector-java-5.1.22-bin.jar")
sys.path.append("/Libs/py4j-0.9.jar")
sys.path.append("/Libs/org.apache.commons.lang_2.6.0.v201205030909.jar")
sys.path.append("/Libs/org.eclipse.cdt.core_5.6.0.201402142303.jar")
sys.path.append("/Libs/org.eclipse.core.contenttype_3.4.200.v20120523-2004.jar")
sys.path.append("/Libs/org.eclipse.core.jobs_3.5.200.v20120521-2346.jar")
sys.path.append("/Libs/org.eclipse.core.resources.win32.x86_3.5.100.v20110423-0524.jar")
sys.path.append("/Libs/org.eclipse.core.resources_3.8.0.v20120522-2034.jar")
sys.path.append("/Libs/org.eclipse.core.runtime_3.8.0.v20120521-2346.jar")
sys.path.append("/Libs/org.eclipse.equinox.common_3.6.100.v20120522-1841.jar")
sys.path.append("/Libs/org.eclipse.equinox.common_3.6.200.v20130402-1505.jar")
sys.path.append("/Libs/org.eclipse.equinox.preferences_3.5.0.v20120522-1841.jar")
sys.path.append("/Libs/org.eclipse.jdt.core_3.8.1.v20120531-0637.jar")
sys.path.append("/Libs/org.eclipse.jdt.ui_3.8.2.v20130107-165834.jar")
sys.path.append("/Libs/org.eclipse.jface.text_3.8.0.v20120531-0600.jar")
sys.path.append("/Libs/org.eclipse.ltk.core.refactoring_3.6.100.v20130605-1748.jar")
sys.path.append("/Libs/org.eclipse.osgi_3.8.0.v20120529-1548.jar")
sys.path.append("/Libs/org.eclipse.text_3.5.0.jar")
sys.path.append("/Libs/bson-3.0.2.jar")
sys.path.append("/Libs/mongodb-driver-3.0.2.jar")
sys.path.append("/Libs/mongodb-driver-core-3.0.2.jar")

# Description: Goes trough mysql database. extracts code snippets and buid an AST of that code. Then, the AST code information are stored in lucene/mongo

from java.sql import ResultSet
from java.io import File
from java.io import IOException
from java.lang import Integer
from java.lang import String
from java.lang import System

from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.analysis.core import KeywordAnalyzer
from org.apache.lucene.analysis.miscellaneous import PerFieldAnalyzerWrapper
from org.apache.lucene.document import Document, Field, StringField
from org.apache.lucene.index import IndexWriter, IndexWriterConfig, CorruptIndexException
from org.apache.lucene.store import SimpleFSDirectory, LockObtainFailedException
from org.apache.lucene.util import Version
from java.util.concurrent import Executors

from GitSearch.MyUtils import unescape_html, tokenize
from GitSearch.Analyzer.PorterAnalyzer import PorterAnalyzer
from GitSearch.Analyzer.JavaCodeAnalyzer import JavaCodeAnalyzer
from GitSearch.Indexer.SOParser import PostParser
from GitSearch.Import.ImportAST import transform_body
from GitSearch.Indexer.Indexer_Counter import Counter
# from GitSearch.Indexer.JavaCodeParser import transform_body /// 이런식으로 옮겨서 하면 엿먹음
from java.sql import SQLException
from java.sql import DriverManager
from java.lang import Class

# Jython cannot read large files (1.6MB)
pool = Executors.newFixedThreadPool(4)

path_notIndexed = "/Users/Falcon/Desktop/New_Indices/Stack_Q_Indices/not_indexed.txt"

def load_so_fail_ids():
	""" Contains a list of stackoverflow discussions which are not indexed by the JavaCodeSnippetIndexer because of failures or non-java snippets """
	with open(path_notIndexed, "r") as f:
		for line in f:
			yield int(line)

def get_db_connection():
	Class.forName("com.mysql.jdbc.Driver").newInstance()
	newConn = DriverManager.getConnection("jdbc:mysql://203.255.81.42:3306/stackoverflow?autoReconnect=true", "seal", "sel535424")
	newConn.setAutoCommit(True)
	return newConn

def index_code_snippet(writer, counter):
	mysql_conn = get_db_connection()
	stmt = mysql_conn.createStatement(ResultSet.TYPE_FORWARD_ONLY, ResultSet.CONCUR_READ_ONLY)
	querySO = """
					SELECT Q.Id as QId, Q.Title, Q.Body as QBody, Q.Tags, Q.ViewCount, Q.Score,
					A.Body as ABody, A.Id as AId
					FROM posts as Q	JOIN posts as A ON Q.Id = A.ParentId
					WHERE A.ParentId IS NOT NULL
					AND Q.AcceptedAnswerId = A.Id
					AND A.Score > 0
					AND A.Body LIKE "%</code>%"
					AND (Q.Tags LIKE "%<java>%" OR Q.Tags LIKE "%<android>%")
					AND	LOWER(Q.Title) NOT LIKE "%not%"
					AND LOWER(Q.Title) NOT LIKE "%why%"
					AND LOWER(Q.Title) NOT LIKE "%error%"
					AND LOWER(Q.Title) NOT LIKE "%no %"
					AND LOWER(Q.Title) NOT LIKE "% install%"
					AND LOWER(Q.Title) NOT LIKE "% can't%"
					AND LOWER(Q.Title) NOT LIKE "% don't%"
					AND LOWER(Q.Title) NOT LIKE "% issue%"
					AND LOWER(Q.Title) NOT LIKE "difference %"
					AND LOWER(Q.Title) NOT LIKE "unable %"
					AND LOWER(Q.Title) NOT LIKE "debug %"
					AND LOWER(Q.Title) NOT LIKE "exception %"
					AND LOWER(Q.Title) NOT LIKE "best way %"
				"""  # Returns nearly 400,000 posts
	# AND A.Body LIKE "%</code>%"
	# AND Q.CreationDate < "2014-01-01 00:00:00"
	# AND A.CreationDate < "2013-06-01 00:00:00"

	stmt.setFetchSize(Integer.MIN_VALUE)
	resultSet = stmt.executeQuery(querySO)
	i = 0
	not_indexed = []

	#for failed_id in load_so_fail_ids():

	failed_id_gen = load_so_fail_ids()
	failed_id = next(failed_id_gen, None)
	count = 0
	while resultSet.next():
		i += 1
		if i % 1000 == 0:
			print "C: %s" % (i)
			print "typed_method_call : " + str(counter.typed_method_call_count)

		question_id = resultSet.getInt("QId")
		question_body = resultSet.getString("QBody")
		answer_id = resultSet.getInt("AId")
		title = resultSet.getString("Title")
		view_count = resultSet.getString("ViewCount")

		if question_id == failed_id:
			failed_id = next(failed_id_gen, None)
			continue

		document = Document()
		document.add(StringField("question_id", String.valueOf(question_id), Field.Store.YES))

		###To improve the precision of the results..
		#Addtional manual pre-processing in PostParser(question_body)

		p = PostParser(question_body)  # question_body에는 질문 바디의 모든 p태그 내용이 들어감.
		document.add(Field("description", p.get_description(), Field.Store.YES, Field.Index.ANALYZED, Field.TermVector.WITH_POSITIONS_OFFSETS))
		document.add(StringField("answer_id", String.valueOf(answer_id), Field.Store.YES))
		document.add(Field("title", title, Field.Store.YES, Field.Index.ANALYZED))
		document.add(Field("view_count", view_count, Field.Store.YES, Field.Index.ANALYZED))

		#참고.. 링크는 인덱싱 할 때 무시해야함. 26305가 왜 인덱싱이 안되는지 궁금하다..

		# add_code_into_document(document, question_body)
		# writer.addDocument(document)

        # 코드가 자바 Parser에서 파싱할 수 있는 코드를 가지고 있으면 성공 아니면, 아예 인덱싱 되지 않음.
		if add_code_into_document(document, question_body, counter):
			writer.addDocument(document)
			# print question_id
		else:
			not_indexed.append(question_id)
		count += 1

	write_file(not_indexed)
	print "Total Count : %d" % count
	print "Not Index: %s" % len(not_indexed)

def write_file(not_indexed):
	with open(path_notIndexed, "a") as f:
		for not_index in not_indexed:
			if not_index:
				f.write(str(not_index)+"\n")

def add_code_into_document(document, body, counter):
	asts, code_hints = transform_body(body)
	flag = False

	for ast in asts:
		for method_call in ast["typed_method_call"]:
			if method_call:
				document.add(Field("typed_method_call", method_call, Field.Store.YES, Field.Index.ANALYZED))
				counter.typed_method_call_count += 1
				flag = True

		for extend in ast["extends"]:
			if extend:
				document.add(Field("extends", extend, Field.Store.YES, Field.Index.ANALYZED))
				counter.extends_count += 1

		for used_class in ast["used_classes"]:
			if used_class:
				document.add(Field("used_classes", used_class, Field.Store.YES, Field.Index.ANALYZED))
				counter.used_classes_count += 1

		for method in ast["methods"]:
			if method:
				document.add(Field("methods", method, Field.Store.YES, Field.Index.ANALYZED))
				counter.methods_count += 1
				flag = True

		for method in ast["methods_called"]:
			if method:
				document.add(Field("methods_called", method, Field.Store.YES, Field.Index.ANALYZED))
				counter.methods_called_count += 1
				flag = True

		if "comments" in ast:
			for used_class in ast["comments"]:
				document.add(Field("comments", unescape_html(used_class), Field.Store.NO, Field.Index.ANALYZED))
				counter.comments_count += 1

		for instance in ast["class_instance_creation"]:
			if instance:
				document.add(Field("class_instance_creation", instance, Field.Store.YES, Field.Index.ANALYZED))
				counter.class_instance_creation_count += 1
				flag = True

		# for literal in ast["literals"]:
		# 	if literal:
		# 		document.add(StringField("literals", literal, Field.Store.YES))
		# 		counter.literals_count += 1
	hints = []
	for h in code_hints:
		for token in tokenize(h):
			if 1 < len(token) < 20:
				hints.append(token)
	for hint in set(hints):
		document.add(Field("code_hints", hint, Field.Store.YES, Field.Index.ANALYZED))
		counter.code_hints_count += 1

	return flag

def main():
	try:
		print "Indexing..."
		indexDestination = File("/Users/Falcon/Desktop/New_Indices/Stack_Q_Indices")
		# writer = IndexWriter(SimpleFSDirectory(indexDestination), StandardAnalyzer(), True, IndexWriter.MaxFieldLength.UNLIMITED)
		analyzer = PorterAnalyzer(StandardAnalyzer(Version.LUCENE_CURRENT))
		a = {"typed_method_call": KeywordAnalyzer(), "extends": KeywordAnalyzer(),
			 "used_classes": KeywordAnalyzer(), "methods": KeywordAnalyzer(),
			 "class_instance_creation": KeywordAnalyzer(), "methods_called": KeywordAnalyzer(),
			 "view_count": KeywordAnalyzer(), "code_hints": JavaCodeAnalyzer()}
		#KeywordAnalyzer : 필드의 전체 원문을 하나의 토큰으로 처리
		wrapper_analyzer = PerFieldAnalyzerWrapper(analyzer, a)
		#PerFieldAnalyzerWrapper : 필드별로 분석기를 지정하는 기능을 지원하는 클래스
		config = IndexWriterConfig(Version.LUCENE_CURRENT, wrapper_analyzer)
		config.setInfoStream(System.out)  # 루씬 색인작업 디버깅 // 루크라는 도구를 사용해서 루씬 색인 관리를 할 수도 있음..
		writer = IndexWriter(SimpleFSDirectory(indexDestination), config)

		counter = Counter()
		index_code_snippet(writer, counter)
		writer.commit()

		writer.close()
		print "Done"
		print str(counter)

	except CorruptIndexException as e:  # when index is corrupt
		e.printStackTrace()
	except LockObtainFailedException as e:  # when other writer is using the index
		e.printStackTrace()
	except IOException as e:  # when directory can't be read/written
		e.printStackTrace()
	except SQLException as e:  # when Database error occurs
		e.printStackTrace()



if __name__ == '__main__':
	main()


# 	original_question_query = """
# 					SELECT Id, AcceptedAnswerId, Title, Body, Tags, ViewCount, Score
# 					FROM posts
# 					WHERE ParentId IS NULL
# 					AND AcceptedAnswerId IS NOT NULL
# 					AND Score >= 0
# 					AND (Tags LIKE "%<java>%" OR Tags LIKE "%<android>%")
# 					AND	LOWER(Title) NOT LIKE "%not%"
# 					AND LOWER(Title) NOT LIKE "%why%"
# 					AND LOWER(Title) NOT LIKE "%error%"
# 					AND LOWER(Title) NOT LIKE "%no %"
# 					AND LOWER(Title) NOT LIKE "% install%"
# 					AND LOWER(Title) NOT LIKE "% can't%"
# 					AND LOWER(Title) NOT LIKE "% don't%"
# 					AND LOWER(Title) NOT LIKE "% issue%"
# 					AND LOWER(Title) NOT LIKE "difference %"
# 					AND LOWER(Title) NOT LIKE "unable %"
# 					AND LOWER(Title) NOT LIKE "debug %"
# 					AND LOWER(Title) NOT LIKE "exception %"
# 					AND LOWER(Title) NOT LIKE "best way %"
# """