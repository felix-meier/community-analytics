import os
import time
import csv
import pandas
import numpy
import ast
import ssl
import certifi
import glob
import sys
import json
import itertools
import hashlib
from functools import reduce
from math import floor
from datetime import datetime

master = 'master/csv'
metrics = 'metrics/csv'
batch = None
stage = None
sign_token = None
access_token = None
user_token = None

def dd_makedirs():
  try:
    os.makedirs('data/'+batch+'/api');
  except Exception:
    print("/api exists");
  try:
    os.makedirs('data/'+batch+'/csv');
  except Exception:
    print("/csv exists");
  try:
    os.makedirs('data/'+batch+'/metrics');
  except Exception:
    print("/metrics exists");
  try:
    os.makedirs('data/'+batch+'/json');
  except Exception:
    print("/json exists");
  try:
    os.makedirs('data/'+batch+'/metadata');
  except Exception:
    print("/metadata exists");

def sortfile_key(file):
  return int(file[-21:-5]);

def dd_backupfile(filename):
  backuptime = datetime.now().strftime('%Y%m%d%H%M%S')
  # move file to a backup
  os.rename('data/master/csv/'+filename+'.csv','data/master/csv/'+filename+'-'+batch+'.csv')

def dd_writefile(key,filename,pdf,index=False):
  with open('data/'+key+'/'+filename+'.csv','a',encoding='utf-8') as f:
    pdf.to_csv(f,index=index,quoting=csv.QUOTE_ALL,mode='a',header=f.tell()==0);

def dd_readfile(key,filename):
  try:
    pdf = pandas.read_csv('data/'+key+'/'+filename+'.csv',dtype={'TS':str,'THREAD_TS':str,'ts':str,'thread_ts':str},encoding='utf-8');
    return pdf;
  except Exception as err:
    print(err);
    return pandas.DataFrame();

def dd_readref(filename):
  try:
    pdf = pandas.read_csv('../../../../../data/'+filename+'.csv',encoding='utf-8');
    return pdf;
  except Exception as err:
    print(err);
    return pandas.DataFrame();

def epochstr_to_isostr(s):
  return time.strftime('%Y-%m-%dT%H:%M:%S.000',time.localtime(float(s)));
  # return datetime.utcfromtimestamp(time.gmtime(float(s)));

def dd_userdata(result):
  filename = "user_data";
  try:
    users = result['members'];
    pdf = pandas.DataFrame.from_records(users);
    ddpdf = pdf[['id','name','real_name','tz']];
    dd_writefile(master,filename,ddpdf)
  except Exception as err:
    print('Error')
    print(err)

def dd_channeldata(result):
  filename = "channel_data";
  try:
    channels = result['channels'];
    l = []
    for channel in channels:
      id = channel['id'];
      channel_type = ''
      channel_class = ''
      channel_name  = ''
      if 'is_channel' in channel and channel['is_channel']:
        channel_type = 'channel';
      if 'is_mpim' in channel and channel['is_mpim']:
        channel_type = 'mpim';
      if 'is_im' in channel and channel['is_im']:
        channel_type = 'im';
      if 'is_private' in channel and channel['is_private']:
        channel_class = 'confidential';
      else:
        channel_class = 'public';
      if 'name' in channel:
        channel_name = channel['name'] 
      if 'is_archived' in channel:
        is_archived = channel['is_archived'] 
      if 'is_private' in channel:
        is_private = channel['is_private'] 
      l.append({'id': id, 'name': channel_name, 'type': channel_type, 'class': channel_class, 'is_archived': is_archived, 'is_private': is_private });
      retrieve_messages(id);
    ddpdf = pandas.DataFrame.from_records(l);
    if len(ddpdf.index) > 0:
      dd_writefile(master,filename,ddpdf)
  except Exception as err:
    print('Error')
    print(err)

def dd_messagedata(id,result):
  filename = "message_data";
  try:
    messages = result['messages']
    for message in result['messages']:
      if 'reply_count' in message and message['reply_count'] != None and message['reply_count'] > 0:
        print('replies:'+message['ts']+','+str(message['reply_count']));
        retrieve_threads(id,message['ts']);
      else:
        dd_reactiondata(id,message)
    ddpdf = pandas.DataFrame.from_records(messages);
    if len(ddpdf.index) > 0:
      ddpdf['channel'] = id;
      if 'type' not in ddpdf:
        ddpdf['type'] = None;
      if 'subtype' not in ddpdf:
        ddpdf['subtype'] = None;
      if 'ts' not in ddpdf:
        ddpdf['ts'] = None;
      if 'thread_ts' not in ddpdf:
        ddpdf['thread_ts'] = None;
      if 'reply_count' not in ddpdf:
        ddpdf['reply_count'] = None;
      if 'user' not in ddpdf:
        ddpdf['user'] = None;
      if 'text' not in ddpdf:
        ddpdf['text'] = None;
      ddpdf['time'] = ddpdf['ts'].apply(epochstr_to_isostr);
      ddpdf = ddpdf[['channel','type','subtype','ts','thread_ts','time','reply_count','user','text']];
      dd_writefile(master,filename,ddpdf)
  except Exception as err:
    print('Error - dd_messagedata')
    print(err)

def dd_threaddata(id,ts,result):
  filename = "thread_data";
  try:
    messages = result['messages']
    for row in messages:
      dd_reactiondata(id,row)
    ddpdf = pandas.DataFrame.from_records(messages);
    if len(ddpdf.index) > 0:
      ddpdf['channel'] = id;
      if 'type' not in ddpdf:
        ddpdf['type'] = None;
      if 'subtype' not in ddpdf:
        ddpdf['subtype'] = None;
      if 'ts' not in ddpdf:
        ddpdf['ts'] = None;
      if 'thread_ts' not in ddpdf:
        ddpdf['thread_ts'] = None;
      if 'user' not in ddpdf:
        ddpdf['user'] = None;
      if 'text' not in ddpdf:
        ddpdf['text'] = None;
      ddpdf['time'] = ddpdf['ts'].apply(epochstr_to_isostr);
      ddpdf = ddpdf[['channel','type','subtype','ts','thread_ts','time','user','text']];
      # print(ddpdf);
      dd_writefile(master,filename,ddpdf)
  except Exception as err:
    print('Error')
    print(err)

def dd_reactiondata(id,row):
  filename = "reaction_data";
  try:
    # print(row)
    if 'reactions' in row and row['reactions'] != None:
      l = []
      for reaction in row['reactions']:
        for user in reaction['users']:
          if 'thread_ts' in row:
            thread_ts = row['thread_ts']
          else:
            thread_ts = ''
          l.append({'channel':id, 'ts': str(row['ts']), 'thread_ts': str(thread_ts), 'user': user, 'reaction':str(reaction['name'])});
      pdf = pandas.DataFrame.from_records(l);
      if len(pdf.index) > 0:
        dd_writefile(master,filename,pdf)
  except Exception as err:
    print('Error - dd_reactiondata')
    print(err)

def dd_filedata(result):
  filename = "file_data";
  try:
    files = result['files']
    lc = [];
    for row in files:
      if 'channels' in row and row['channels'] != None:
        for channel in row['channels']:
          lc.append({'id': row['id'], 'channel': channel, 'name': row['name'], 'time': epochstr_to_isostr(row['timestamp']), 'user': row['user']});
    print('files downloaded mapped to channels - '+str(len(lc)))
    pdf = pandas.DataFrame.from_records(lc);
    dd_writefile(master,filename,pdf)
  except Exception as err:
    print('Error')
    print(err)

def dd_polldata(id,result):
  filename = "poll_data";
  try:
    messages = result['messages']
    lc = [];
    poll_id = None;
    poll_text = None;
    for message in messages:
      if 'subtype' in message and message['subtype'] == 'bot_message' and 'blocks' in message and message['blocks'] != None:
        for block in message['blocks']:
          if 'block_id' in block and block['block_id'][0:5] == 'poll-':
            print(block['block_id']);
            if block['block_id'][-4:] == 'menu':
              poll_id = block['block_id'][:-15];
              poll_text = block['text']['text'];
            else:
              print(poll_id);
              print(block['text']['text'].split('`'));
              vote = block['text']['text'].split('`');
              lc.append({'poll_id': poll_id, 'ts': message['ts'], 'time': epochstr_to_isostr(message['ts']), 'text': poll_text, 'vote_item': vote[0].strip(), 'vote_count': int(vote[1]) if len(vote) > 1 else 0 });
    pdf = pandas.DataFrame.from_records(lc);
    dd_writefile(master,filename,pdf)
  except Exception as err:
    print('Error - dd_polldata')
    print(err)

def retrieve_userdata():
  try:
    loop = True;
    files = glob.glob('data/'+batch+'/api/user_list*.json')
    for file in files:
      print('retrieving user_data - '+file);
      a = 0;
      result = None;
      while a < 3 and result == None:
        try:
          f = open(file,'r');
          result = ast.literal_eval(f.read());
        except Exception as err:
          print('error in file io')
          print(err);
          a += 1
          result = None
          time.sleep(0.1)
      if result == None:
        exit(-1);
      dd_userdata(result);
  except Exception as err:
    print('Error')
    print(err)

def retrieve_channeldata():
  try:
    loop = True;
    files = glob.glob('data/'+batch+'/api/conversation_list*.json')
    files.sort(key = sortfile_key)
    # assuming it is in order of "filename" - though there are conflicting messages
    for file in files:
      print('retrieving channel_data - '+file);
      a = 0;
      result = None
      while a < 3 and result == None:
        try:
          f = open(file,'r');
          result = ast.literal_eval(f.read());
        except Exception as err:
          print('error in file io')
          print(err);
          a += 1
          result = None
          time.sleep(0.1)
      if result == None:
        exit(-1);
      dd_channeldata(result);
  except Exception as err:
    print('Error')
    print(err)

def retrieve_messages(id):
  try:
    loop = True;
    files = glob.glob('data/'+batch+'/api/conversation_history-'+id+'*.json')
    files.sort(key = sortfile_key)
    for file in files:
      print('retrieving message_data for channel: '+id+' '+file);
      a = 0;
      result = None
      while a < 3 and result == None:
        try:
          f = open(file,'r');
          result = ast.literal_eval(f.read());
        except Exception as err:
          print('error in file io')
          print(err);
          a += 1
          result = None
          time.sleep(0.1)
      if result == None:
        exit(-1);
      dd_messagedata(id,result);
  except Exception as err:
    print('Error')
    print(err)

def retrieve_threads(id,ts):
  try:
    loop = True;
    files = glob.glob('data/'+batch+'/api/conversation_replies-'+id+'_'+ts+'*.json')
    files.sort(key = sortfile_key)
    for file in files:
      print('retrieving thread_data for message:'+id+' '+ts+' '+file);
      a = 0;
      result = None
      while a < 3 and result == None:
        try:
          f = open(file,'r');
          result = ast.literal_eval(f.read());
        except Exception as err:
          print('error in retrieve thread call')
          print(err);
          a += 1
          result = None
          time.sleep(0.1)
      if result == None:
        exit(-1);
      dd_threaddata(id,ts,result);
  except Exception as err:
    print('Error')
    print(err)

def retrieve_filedata():
  try:
    loop = True;
    files = glob.glob('data/'+batch+'/api/files_list-*.json')
    files.sort(key = sortfile_key)
    for file in files:
      print('retrieving file_data: '+file);
      a = 0;
      result = None
      while a < 3 and result == None:
        try:
          f = open(file,'r');
          result = ast.literal_eval(f.read());
        except Exception as err:
          print('error in retrieve file call')
          print(err);
          a += 1
          result = None
          time.sleep(0.1)
      if result == None:
        exit(-1);
      dd_filedata(result);
  except Exception as err:
    print('Error')
    print(err)

def retrieve_polldata(botid):
  try:
    loop = True;
    files = glob.glob('data/'+batch+'/api/conversation_history-C010VKAQ96V*.json')
    files.sort(key = sortfile_key)
    for file in files:
      print('retrieving poll_data for channel: '+botid+' '+file);
      a = 0;
      result = None
      while a < 3 and result == None:
        try:
          f = open(file,'r');
          result = ast.literal_eval(f.read());
        except Exception as err:
          print('error in file io')
          print(err);
          a += 1
          result = None
          time.sleep(0.1)
      if result == None:
        exit(-1);
      dd_polldata(botid,result);
  except Exception as err:
    print('Error')
    print(err)

def convert_to_json():
  try:
    loop = True;
    try:
      os.makedirs('data/'+batch+'/json');
    except Exception as err:
      print('directory exists');
    files = glob.glob('data/'+batch+'/api/*.json')
    for file in files:
      print('retrieving file_data: '+file);
      a = 0;
      result = None
      while a < 3 and result == None:
        try:
          fi = open(file,'r');
          result = ast.literal_eval(fi.read());
          json_result = json.dumps(result)
          outfile = file.replace('/api/','/json/');
          fo = open(outfile,'w')
          fo.write(str(json_result))
          fo.close();
          fi.close();
        except Exception as err:
          print('error in file conversion')
          print(err);
          a += 1
          result = None
          time.sleep(0.1)
      if result == None:
        exit(-1);
  except Exception as err:
    print('Error')
    print(err)

def _merge_data(filename,index_cols,cols):
  # for merging 
  # - we will append new records
  # - we will update existing records based upon key (just take the latest record even if it is the same)
  # - we will not delete old records
  try:
    inpdf = dd_readfile(master,filename);
    inpdf = inpdf.sort_values(index_cols);
    print(inpdf);
    mpdf = dd_readfile('master/csv',filename);
    print(mpdf);
    if mpdf.empty and inpdf.empty == False:
      dd_writefile('master/csv',filename,inpdf);
      print('initialising users dataset: '+str(len(inpdf)));
    else:
      mpdf = mpdf.sort_values(index_cols);
      df = inpdf.merge(mpdf.drop_duplicates(), on=index_cols, how='left', indicator=True)
      merged_cols = [];
      merged_rename_cols = {};
      for col in cols:
        if col not in index_cols:
          merged_cols.append(col+'_x'); 
          merged_rename_cols[col+'_x'] = col;
        else:
          merged_cols.append(col); 
          merged_rename_cols[col] = col;
      insertpdf = df[df['_merge'] == 'left_only'];
      insertpdf = insertpdf[merged_cols];
      insertpdf = insertpdf.rename(columns=merged_rename_cols);
      insertpdf = insertpdf.drop_duplicates();
      insertpdf = insertpdf.sort_values(index_cols);
      if insertpdf.empty == False:
        dd_writefile(master,filename+'_insert',insertpdf);
        print('adding users: '+str(len(insertpdf)));
      updatepdf = df[df['_merge'] == 'both'];
      updatepdf = updatepdf[merged_cols];
      updatepdf = updatepdf.rename(columns=merged_rename_cols);
      updatepdf = updatepdf.drop_duplicates();
      updatepdf = updatepdf.sort_values(index_cols);
      print(updatepdf);
      if updatepdf.empty == False:
        dd_writefile(master,filename+'_update',updatepdf);
        print('updating users: '+str(len(updatepdf)));
      deltapdf = insertpdf.append(updatepdf,ignore_index=False);
      df = mpdf.merge(deltapdf.drop_duplicates(), on=index_cols, how='left', indicator=True)
      unchangedpdf = df[df['_merge'] == 'left_only'];
      unchangedpdf = unchangedpdf[merged_cols];
      unchangedpdf = unchangedpdf.rename(columns=merged_rename_cols);
      fullpdf = unchangedpdf.append(deltapdf,ignore_index=False);
      fullpdf = fullpdf.drop_duplicates();
      fullpdf = fullpdf.sort_values(index_cols);
      if fullpdf.empty == False:
        dd_backupfile(filename);
        dd_writefile('master/csv',filename,fullpdf);
        print('merging: '+str(len(fullpdf)));
  except Exception as err:
    print('Error')
    print(err)

def merge_userdata():
  filename = 'user_data' 
  cols = ['id','name','real_name','tz']
  index_cols = ['id']
  print('merging user dataset');
  _merge_data(filename,index_cols,cols);

def merge_channeldata():
  filename = 'channel_data'
  cols = ["id","name","type","class","is_archived","is_private"]
  index_cols = ["id"]
  print('merging channel dataset');
  _merge_data(filename,index_cols,cols);

def merge_messagedata():
  filename = 'message_data'
  cols = ["channel","type","subtype","ts","thread_ts","time","reply_count","user","text"]
  index_cols = ["channel","ts"]
  print('merging message dataset');
  _merge_data(filename,index_cols,cols);

def merge_threaddata():
  filename = 'thread_data'
  cols = ["channel","type","subtype","ts","thread_ts","time","user","text"]
  index_cols = ["channel","ts"]
  print('merging thread dataset');
  _merge_data(filename,index_cols,cols);

def merge_reactiondata():
  filename = 'reaction_data'
  cols = ["channel","ts","thread_ts","user","reaction"]
  index_cols = ["ts"]
  print('merging reaction dataset');
  _merge_data(filename,index_cols,cols);

def merge_filedata():
  filename = 'file_data'
  cols = ["id","channel","name","time","user"]
  index_cols = ["id","channel"]
  print('merging channel dataset');
  _merge_data(filename,index_cols,cols);

def merge_polldata():
  filename = 'poll_data'
  cols = ["poll_id","ts","time","text","vote_item","vote_count"]
  index_cols = ["poll_id","vote_item"]
  print('merging channel dataset');
  _merge_data(filename,index_cols,cols);

def create_conversationdata():
  filename = "conversation_data";
  try:
    message_pdf = dd_readfile(master,'message_data');
    user_pdf = dd_readfile(master,'user_data');
    thread_pdf = dd_readfile(master,'thread_data');

    zone_ref_pdf = dd_readref('zone');
    country_ref_pdf = dd_readref('country');

    # Use only subset of information (and create identical columns)
    message_part_pdf = message_pdf[['channel','type','subtype','ts','thread_ts','time','user','text']];
    thread_part_pdf = thread_pdf[['channel','type','subtype','ts','thread_ts','time','user','text']];
    # Merge message and thread data
    conversation_part_pdf = message_part_pdf.append(thread_part_pdf,ignore_index=False);
    conversation_part_pdf = conversation_part_pdf.drop_duplicates();
    # From user data, split as a method to create default country (if timezone is not recognised).
    tz_split = user_pdf['tz'].str.split('/',expand=True);
    # Merge to create richer iso information
    iso_ref_pdf = zone_ref_pdf.merge(country_ref_pdf,left_on='ISO',right_on='ISO2');
    # Merge iso information with user (based upon timezone).
    user_geo_pdf = user_pdf.merge(iso_ref_pdf,how='left',left_on='tz',right_on='TZ');
    # Add country and city based upon user data timezone
    user_geo_pdf['country']  = tz_split[0];
    user_geo_pdf['city']  = tz_split[1];
    # Mask NAN values of country based upon timezone information
    user_geo_pdf['COUNTRY'] = user_geo_pdf['COUNTRY'].mask(pandas.isnull, user_geo_pdf['country']);
    # Merge user data with conversation data based upon user id
    conversation_geo_pdf = conversation_part_pdf.merge(user_geo_pdf,how='left',left_on='user',right_on='id');
    # Add a column (replica of ts) that can be used as an number
    conversation_geo_pdf['ts_int'] = conversation_geo_pdf['ts']
    # Select columns
    conversation_pdf = conversation_geo_pdf[['channel','type','subtype','ts','thread_ts','ts_int','time','user','real_name','name','text','city','COUNTRY','ISO']];
    # Rename columns
    ddpdf = conversation_pdf.rename(columns={'channel':'CHANNEL','type':'TYPE','subtype':'SUBTYPE','ts':'TS','thread_ts':'THREAD_TS','ts_int':'TS_INT','time':'TIME','user':'USER','real_name':'REAL_NAME','name':'NAME','text':'TEXT','city':'CITY','COUNTRY':'COUNTRY','ISO':'ISO'});

    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error');
    print(err);

def create_nodedata():
  filename = "node_data";
  try:
    channel_pdf = dd_readfile(master,'channel_data');
    user_pdf = dd_readfile(master,'user_data');

    zone_ref_pdf = dd_readref('zone');
    country_ref_pdf = dd_readref('country');

    # From user data, split as a method to create default country (if timezone is not recognised).
    tz_split = user_pdf['tz'].str.split('/',expand=True);
    # Merge to create richer iso information
    iso_ref_pdf = zone_ref_pdf.merge(country_ref_pdf,left_on='ISO',right_on='ISO2');
    # Merge iso information with user (based upon timezone).
    user_geo_pdf = user_pdf.merge(iso_ref_pdf,how='left',left_on='tz',right_on='TZ');
    # Augment columns for union 
    # Add country and city based upon user data timezone
    user_geo_pdf['country']  = tz_split[0];
    user_geo_pdf['city']  = tz_split[1];
    # Mask NAN values of country based upon timezone information
    user_geo_pdf['COUNTRY'] = user_geo_pdf['COUNTRY'].mask(pandas.isnull, user_geo_pdf['country']);
    # Add "null" columns for union
    user_geo_pdf['type'] = 'user'
    user_geo_pdf['channel_type'] = None
    user_geo_pdf['channel_class'] = None
    user_part_pdf = user_geo_pdf[['id','name','type','real_name','ISO','COUNTRY','city','channel_type','channel_class']];
    # Augment columns for union 
    channel_pdf = channel_pdf.rename(columns={'type':'channel_type','class':'channel_class'});
    channel_pdf['type'] = 'channel'
    channel_pdf['name'] = channel_pdf['name'].mask(pandas.isnull, channel_pdf['id']);
    channel_pdf['real_name'] = channel_pdf['name']
    # Add "null" columns for union
    channel_pdf['timezone'] = None
    channel_pdf['ISO'] = None
    channel_pdf['COUNTRY'] = None
    channel_pdf['city'] = None
    channel_part_pdf = channel_pdf[['id','name','type','real_name','ISO','COUNTRY','city','channel_type','channel_class']];
    # Merge user and channel nodes
    ddpdf = user_part_pdf.append(channel_part_pdf,ignore_index=True);
    # Rename columns
    ddpdf = ddpdf.rename(columns={'id':'ID','name':'LABEL','type':'TYPE','real_name':'NAME','ISO':'ISO','COUNTRY':'COUNTRY','city':'CITY','channel_type':'CHANNEL_TYPE','channel_class':'CHANNEL_CLASS'});

    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error');
    print(err);

def create_edgedata():
  filename = "edge_data";
  try:
    conversation_pdf = dd_readfile(metrics,'conversation_data');
    c1_pdf = conversation_pdf.copy();
    reaction_pdf = dd_readfile(master,'reaction_data');
    tag_pdf = dd_readfile(metrics,'tag_data');
    c1_pdf_1 = c1_pdf[c1_pdf['SUBTYPE'] == 'thread_broadcast'];
    c1_pdf_2 = c1_pdf[c1_pdf['SUBTYPE'].isnull()];
    c1_pdf = c1_pdf_1.append(c1_pdf_2,ignore_index=False);
    c2_pdf = c1_pdf.copy();
    c2_pdf = c2_pdf[c2_pdf['THREAD_TS'].notnull()];
    c4_pdf = c1_pdf.merge(c2_pdf,how='left',left_on='THREAD_TS',right_on='TS');
    # print(c4_pdf.shape);
    c4_pdf = c4_pdf[c4_pdf['USER_x'] != c4_pdf['USER_y']];
    c4_pdf = c4_pdf[['CHANNEL_x','USER_x','USER_y']];
    c4_pdf['USER_y'] = c4_pdf['USER_y'].mask(pandas.isnull, c4_pdf['CHANNEL_x']);
    c4_pdf['RELATE'] = 'interacts';
    c4_pdf = c4_pdf.rename(columns={'CHANNEL_x':'CHANNEL','USER_x':'SOURCE','USER_y':'TARGET','RELATE':'RELATE'});
    # print(c4_pdf.shape);
    c3_pdf = c1_pdf.copy();
    c5_pdf = c3_pdf.merge(reaction_pdf,how='left',left_on='TS',right_on='ts');
    c5_pdf = c5_pdf[c5_pdf['user'].notnull()];
    c5_pdf = c5_pdf[['CHANNEL','USER','user']];
    c5_pdf['RELATE'] = 'reacts';
    c5_pdf = c5_pdf.rename(columns={'CHANNEL':'CHANNEL','USER':'SOURCE','user':'TARGET','RELATE':'RELATE'});
    # print(c5_pdf.shape);
    c6_pdf = c1_pdf.copy();
    c6_pdf = c6_pdf.merge(tag_pdf,how='left',on='TS');
    c6_pdf = c6_pdf[c6_pdf['USER'].notnull()];
    c6_pdf = c6_pdf[c6_pdf['TYPE_y'] == 'user'];
    c6_pdf = c6_pdf[['CHANNEL_x','USER','TAG']];
    c6_pdf['RELATE'] = 'refers';
    c6_pdf = c6_pdf.rename(columns={'CHANNEL_x':'CHANNEL','USER':'SOURCE','TAG':'TARGET','RELATE':'RELATE'});
    # print(c6_pdf.shape);
    # print(c6_pdf);
    ddpdf = c4_pdf.append(c5_pdf,ignore_index=True);
    ddpdf = ddpdf.append(c6_pdf,ignore_index=True);
    print(ddpdf);

    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error');
    print(err);

def aggregate_conversationdata():
  try:
    channel_pdf = dd_readfile(master,'channel_data');
    user_pdf = dd_readfile(master,'user_data');

    c1_pdf = dd_readfile(metrics,'conversation_data');
    c1_pdf_1 = c1_pdf[c1_pdf['SUBTYPE'] == 'thread_broadcast'];
    c1_pdf_2 = c1_pdf[c1_pdf['SUBTYPE'].isnull()];
    c1_pdf = c1_pdf_1.append(c1_pdf_2,ignore_index=False);
    agg_pdf = c1_pdf.groupby('CHANNEL').count()[['TS','THREAD_TS']];
    # print(agg_pdf);
    dd_writefile(metrics,'aggr_by_channel',agg_pdf,True);
    agg_pdf = c1_pdf.groupby(['CHANNEL','USER']).count()[['TS','THREAD_TS']];
    # print(agg_pdf);
    dd_writefile(metrics,'aggr_by_channel_user',agg_pdf,True);
    unique_pdf = agg_pdf.copy();
    unique_pdf.reset_index(inplace=True);
    unique_pdf = unique_pdf.groupby(['CHANNEL']).count()[['USER']];
    print(unique_pdf);
    dd_writefile(metrics,'number_channel_user',unique_pdf,True);
    max_pdf = agg_pdf.groupby(['CHANNEL']).max()[['TS']];
    # print(max_pdf);
    m1_pdf = agg_pdf.merge(max_pdf,how='inner',left_index=True,right_index=True);
    m1_pdf = m1_pdf[m1_pdf['TS_x'] == m1_pdf['TS_y']];
    print(m1_pdf);
    m1_pdf.reset_index(inplace=True);
    m2_pdf = m1_pdf.merge(user_pdf,how='left',right_on='id',left_on='USER');
    m3_pdf = m2_pdf.merge(channel_pdf,how='left',right_on='id',left_on='CHANNEL');
    m4_pdf = m3_pdf[['CHANNEL','name_y','USER','real_name','TS_x']];
    m4_pdf = m4_pdf.rename(columns={'CHANNEL':'CHANNEL_ID','name_y':'CHANNEL_NAME','USER':'USER_ID','real_name':'USER_NAME','TS_x':'TS'});
    # print(m4_pdf);
    dd_writefile(metrics,'max_by_channel_user',m4_pdf);
  except Exception as err:
    print('Error');
    print(err);

def create_timediff_conversations():
  filename = "conversation_timediff_data";
  try:
    df = dd_readfile(metrics,'conversation_data');
    df = df.sort_values(['CHANNEL','TS'],ascending=(True,True));
    df['TIME_TS'] = pandas.to_datetime(df['TIME']);
    # print(df);
    ddf = df[['CHANNEL','TIME_TS']];
    # print(ddf);
    # print(ddf.dtypes);
    ddf = ddf.groupby('CHANNEL').diff();
    ddf['TIME_TS'] = ddf['TIME_TS'] / numpy.timedelta64(1, 's');
    ddf['TIME_TS'] = ddf['TIME_TS'].mask(pandas.isnull, 0);
    # print(ddf);
    # print(ddf.dtypes);
    df = df.merge(ddf,left_index=True,right_index=True);
    # print(df);
    # print(df.dtypes);
    ddpdf = df[['CHANNEL','TYPE','SUBTYPE','TS','THREAD_TS','TS_INT','TIME','USER','REAL_NAME','NAME','TEXT','CITY','COUNTRY','ISO','TIME_TS_y']];
    ddpdf = ddpdf.rename(columns={'TIME_TS_y':'DIFF'});
    # print(ddpdf);
    # print(ddpdf.dtypes);
    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error');
    print(err);

def create_timediff_threads():
  filename = "threads_timediff_data";
  try:
    df = dd_readfile(metrics,'conversation_data');
    df = df[df['THREAD_TS'].notnull()];
    df = df.sort_values(['CHANNEL','THREAD_TS','TS'],ascending=(True,True,True));
    df['TIME_TS'] = pandas.to_datetime(df['TIME']);
    # print(df);
    ddf = df[['CHANNEL','THREAD_TS','TIME_TS']];
    # print(ddf);
    # print(ddf.dtypes);
    ddf = ddf.groupby(['CHANNEL','THREAD_TS']).diff();
    ddf['TIME_TS'] = ddf['TIME_TS'] / numpy.timedelta64(1, 's');
    ddf['TIME_TS'] = ddf['TIME_TS'].mask(pandas.isnull, 0);
    # print(ddf);
    # print(ddf.dtypes);
    df = df.merge(ddf,left_index=True,right_index=True);
    # print(df);
    # print(df.dtypes);
    ddpdf = df[['CHANNEL','TYPE','SUBTYPE','TS','THREAD_TS','TS_INT','TIME','USER','REAL_NAME','NAME','TEXT','CITY','COUNTRY','ISO','TIME_TS_y']];
    ddpdf = ddpdf.rename(columns={'TIME_TS_y':'DIFF'});
    # print(ddpdf);
    # print(ddpdf.dtypes);
    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error');
    print(err);

def create_timediff_users():
  filename = "users_timediff_data";
  try:
    df = dd_readfile(metrics,'conversation_data');
    df = df[df['THREAD_TS'].notnull()];
    df = df.sort_values(['USER','TS'],ascending=(True,True));
    df['USER_HASH'] = df['USER'].apply(hash);
    df['TIME_TS'] = pandas.to_datetime(df['TIME']);
    # print(df);
    ddf = df[['USER','TIME_TS']];
    # print(ddf);
    # print(ddf.dtypes);
    ddf = ddf.groupby(['USER']).diff();
    ddf['TIME_TS'] = ddf['TIME_TS'] / numpy.timedelta64(1, 's');
    ddf['TIME_TS'] = ddf['TIME_TS'].mask(pandas.isnull, 0);
    # print(ddf);
    # print(ddf.dtypes);
    df = df.merge(ddf,left_index=True,right_index=True);
    # print(df);
    # print(df.dtypes);
    ddpdf = df[['CHANNEL','TYPE','SUBTYPE','TS','THREAD_TS','TS_INT','TIME','USER','USER_HASH','REAL_NAME','NAME','TEXT','CITY','COUNTRY','ISO','TIME_TS_y']];
    ddpdf = ddpdf.rename(columns={'TIME_TS_y':'DIFF'});
    # print(ddpdf);
    # print(ddpdf.dtypes);
    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error');
    print(err);

def aggregate_threads():
  filename = "length_threads_data";
  try:
    df = dd_readfile(metrics,'conversation_data');
    df = df[df['THREAD_TS'].notnull()];
    ddf = df.groupby(['CHANNEL','THREAD_TS']).count()[['TS']];
    ddf.reset_index(inplace=True);
    print(ddf);
    dd_writefile(metrics,'aggr_by_thread',ddf);
    ddf = df.groupby(['CHANNEL','THREAD_TS','USER']).count()[['TS']];
    ddf.reset_index(inplace=True);
    print(ddf);
    dd_writefile(metrics,'aggr_by_thread_user',ddf);
  except Exception as err:
    print('Error');
    print(err);

def extract_tags():
  filename = "tag_data";
  try:
    df = dd_readfile(metrics,'conversation_data');
    udf = dd_readfile(master,'user_data');
    df_1 = df[df['SUBTYPE'] == 'thread_broadcast'];
    df_2 = df[df['SUBTYPE'].isnull()];
    df = df_1.append(df_2,ignore_index=True);
    df = df[['CHANNEL','TS','TEXT']];
    df = df[df['TEXT'].notnull()];
    df = df.set_index('TS');
    utdf = df['TEXT'].str.extractall(r'<@(?P<TAG>.*?)>');
    utdf['TYPE'] = 'user';
    utdf.reset_index(inplace=True);
    utdf = utdf.merge(udf,how='left',left_on='TAG',right_on='id');
    utdf = utdf.rename(columns={'real_name':'NICE_TAG'});
    utdf.reset_index(inplace=True);
    utdf = utdf[['TS','TAG','NICE_TAG','TYPE']];
    ctdf = df['TEXT'].str.extractall(r'<#(?P<TAG>.*?)>');
    ctdf = ctdf['TAG'].str.split('|',expand=True)
    ctdf['TYPE'] = 'channel';
    ctdf = ctdf.rename(columns={0:'TAG',1:'NICE_TAG'});
    ctdf.reset_index(inplace=True);
    ctdf = ctdf[['TS','TAG','NICE_TAG','TYPE']];
    ltdf = df['TEXT'].str.extractall(r'<(?P<TAG>.*?)>');
    ltdf = ltdf[ltdf['TAG'].str.contains('^[^@#]')];
    ltdf = ltdf['TAG'].str.split('|',expand=True)
    ltdf = ltdf.rename(columns={0:'TAG',1:'NICE_TAG'});
    ltdf['TYPE'] = 'link';
    ltdf.reset_index(inplace=True);
    ltdf = ltdf[['TS','TAG','NICE_TAG','TYPE']];
    df.reset_index(inplace=True);
    print(utdf);
    print(ctdf);
    print(ltdf);
    tdf = pandas.concat([utdf,ctdf,ltdf],ignore_index=True)
    print(tdf);
    ddf = df.merge(tdf,how='right',on='TS');
    ddf = ddf[['CHANNEL','TS','TAG','NICE_TAG','TYPE']];
    print(ddf);
    dd_writefile(metrics,filename,ddf);
  except Exception as err:
    print('Error');
    print(err);

def exec_stages():
  dd_makedirs();
  if master != 'master' and (stage == None or stage == 1):
    print('Stage 1 - TRANSFORM / LOAD (INTO CSV AND JSON)');
    try:
      print('transform and load user data');
      retrieve_userdata();
      print('transform and load channel / message / thread  data');
      retrieve_channeldata();
      print('transform and load file data');
      retrieve_filedata();
      print('transform and load poll data from a specific bot id: (argh - fragile) B0115K4AY5B');
      retrieve_polldata('B0115K4AY5B');
      convert_to_json();
    except Exception as err:
      print(err)
      exit(-1);
  else:
    print('skipping Stage 1');

  if master != 'master' and (stage == None or stage <= 2):
    print('Stage 2 - Merge Data');
    try:
      merge_userdata();
      merge_channeldata();
      merge_messagedata();
      merge_threaddata();
      merge_reactiondata();
      merge_filedata();
      merge_polldata();
      print("");
    except Exception as err:
      print(err)
      exit(-1);
  else:
    print('skipping Stage 2');

  if stage == None or stage <= 3:
    print('Stage 3 - CREATE ANALYSIS');
    try:
      create_conversationdata();
      create_timediff_conversations();
      create_timediff_threads();
      create_timediff_users();
      extract_tags();
      create_nodedata();
      create_edgedata();
      print("");
    except Exception as err:
      print(err)
      exit(-1);
  else:
    print('skipping Stage 3');

  if stage == None or stage <= 4:
    print('Stage 4 - CREATE AGGREGATES');
    try:
      aggregate_conversationdata();
      aggregate_threads();
      print("");
    except Exception as err:
      print(err)
      exit(-1);
  else:
    print('skipping Stage 4');

if __name__ == "__main__":
  try:
    sign_token = os.environ['SLACK_SIGN_TOKEN']
    access_token = os.environ['SLACK_ACCESS_TOKEN']
    user_token = os.environ['SLACK_USER_TOKEN']
    # user_token = 'SLACK_USER_TOKEN'  
  except:
    print('no tokens available')

  # ssl_context = ssl.create_default_context(cafile=certifi.where())

  if len(sys.argv) >= 2:
    batch = sys.argv[1]
    master = batch+'/csv'
    metrics = batch+'/metrics'
  else:
    batch = 'master'
  if len(sys.argv) >= 3:
    stage = int(sys.argv[2])

  if batch == None:
    print('no batch id provided');
    exit(-1);
  if stage == None:
    print('run all stages');
  if batch == 'master':
    print('creating master metrics');
    stage = 3

  print('this was executed with batch number '+batch);

  # exec_stages();

