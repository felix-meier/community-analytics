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
from datetime import datetime, timedelta

master = 'master/csv'
metrics = 'metrics/csv'
batch = None
stage = None
sign_token = None
access_token = None
user_token = None
data_home = None
data_type = None

def dd_makedirs():
  try:
    os.makedirs(data_home+'/'+batch+'/api');
  except Exception:
    print("/api exists");
  try:
    os.makedirs(data_home+'/'+batch+'/csv');
  except Exception:
    print("/csv exists");
  try:
    os.makedirs(data_home+'/'+batch+'/metrics');
  except Exception:
    print("/metrics exists");
  try:
    os.makedirs(data_home+'/'+batch+'/json');
  except Exception:
    print("/json exists");
  try:
    os.makedirs(data_home+'/'+batch+'/metadata');
  except Exception:
    print("/metadata exists");

def sortfile_key(file):
  return int(file[-21:-5]);

def dd_setdatahome(home):
  global data_home
  data_home = home;

def dd_setdatatype(type):
  global data_type
  data_type = type;

def dd_backupfile(filename):
  backuptime = datetime.now().strftime('%Y%m%d%H%M%S')
  # move file to a backup
  os.rename(data_home+'/master/csv/'+filename+'.csv',data_home+'/master/csv/'+filename+'-'+batch+'.csv')

def dd_writefile(key,filename,pdf,index=False):
  # newline='' = works with both unix and windows style line endings
  with open(data_home+'/'+key+'/'+filename+'.csv','a',encoding='utf-8',newline='') as f:
    pdf.to_csv(f,index=index,quoting=csv.QUOTE_ALL,mode='a',header=f.tell()==0);

def dd_readfile(key,filename):
  try:
    pdf = pandas.read_csv(data_home+'/'+key+'/'+filename+'.csv',dtype={'ts':str,'thread_ts':str,'batch':str,'id':str,'user':str,'channel':str},encoding='utf-8');
    return pdf;
  except Exception as err:
    print(err);
    return pandas.DataFrame();

def dd_readref(filename):
  try:
    pdf = pandas.read_csv(data_home+'/references/'+filename+'.csv',encoding='utf-8');
    return pdf;
  except Exception as err:
    print(err);
    return pandas.DataFrame();

def epochstr_to_isostr(s):
  epoch = (int(s) >> 22) + 1420070400000
  epoch = round(epoch / 1000)
  isostr = time.strftime('%Y-%m-%dT%H:%M:%S.000',time.localtime(float(epoch)));
  return isostr
  # return datetime.utcfromtimestamp(time.gmtime(float(s)));

def batchstr_to_datetime(s):
  return datetime.strptime(s,'%Y%m%d%H%M%S');

def datetime_to_epochstr(d):
  return d.timestamp();

def dd_userdata(result):
  filename = "user_data";
  try:
    # account for discord/slack differences
    if 'members' in result:
      members = result['members'];
    else:
      members = result
    ll = []
    b = datetime_to_epochstr(batchstr_to_datetime(batch).replace(hour=0,minute=0,second=0,microsecond=0) + timedelta(days=-1))
    for member in members:
      row = {}
      if 'id' in member:
        row.update({'id': member['id']})
      if 'name' in member:
        row['name'] = member['name']
      if 'tz' in member:
        row['tz'] = member['tz']
      if 'profile' in member:
        if 'email' in member['profile']:
          row['email'] = member['profile']['email']
        else:
          row['email'] = ''
      else:
        row['email'] = ''
      if 'real_name' in member:
        row['real_name'] = member['real_name']
      row['batch'] = b
      ll.append(row)
    ddpdf = pandas.DataFrame.from_records(ll)
    # pdf = pandas.DataFrame.from_records(users);
    # ddpdf = pdf[['id','name','real_name','tz']];
    dd_writefile(master,filename,ddpdf)
  except Exception as err:
    print('Error dd')
    print(err)

def dd_channeldata(result):
  filename = "channel_data";
  try:
    if 'channels' in result:
      channels = result['channels'];
    else:
      channels = result
    # accounts for differences between discord and slack
    l = []
    for channel in channels:
      id = channel['id'];
      channel_type = ''
      channel_class = ''
      channel_name  = ''
      is_archived  = ''
      is_private  = 'True'
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
    #filename = "message_data";
    filename = "conversation_history";
    #print(result)
    #try:
    if 'messages' in result:
      result = result['messages']['messages']
    for message in result:
      if 'reply_count' in message and message['reply_count'] != None and message['reply_count'] > 0:
        print('replies:'+message['ts']+','+str(message['reply_count']));
        retrieve_threads(id,message['ts']);
      dd_reactiondata(id,message)
    ddpdf = pandas.DataFrame.from_records(result);
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
      print(ddpdf['time'])
      print(ddpdf['ts'])
      ddpdf = ddpdf[['channel','type','subtype','ts','thread_ts','time','reply_count','user','text']];
      dd_writefile(master,filename,ddpdf)
    #except Exception as err:
    #  print('Error - dd_messagedata')
    #  print(err)

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
    if 'files' in result:
      files = result['files']
    else:
      files = result
    # accounts for differences between discord and slack
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
    files = glob.glob(data_home+'/'+batch+'/api/user_list*.json')
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
    print('Error retrieve')
    print(err)

def retrieve_channeldata():
  try:
    loop = True;
    files = glob.glob(data_home+'/'+batch+'/api/conversation_list*.json')
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
    files = glob.glob(data_home+'/'+batch+'/api/conversation_history-'+id+'*.json')
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
    files = glob.glob(data_home+'/'+batch+'/api/conversation_replies-'+id+'_'+ts+'*.json')
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
    files = glob.glob(data_home+'/'+batch+'/api/files_list-*.json')
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
    files = glob.glob(data_home+'/'+batch+'/api/conversation_history-C010VKAQ96V*.json')
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
      os.makedirs(data_home+'/'+batch+'/json');
    except Exception as err:
      print('directory exists');
    files = glob.glob(data_home+'/'+batch+'/api/*.json')
    for file in files:
      print('retrieving file_data: '+file);
      a = 0;
      result = None
      while a < 3 and result == None:
        try:
          fi = open(file,'r');
          result = ast.literal_eval(fi.read());
          json_result = json.dumps(result)
          outfile = file.replace('/api','/json');
          print(outfile)
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

def _merge_data(filename,index_cols,cols,existing_cols=[]):
  # for merging
  # - we will append new records
  # - we will update existing records based upon key (just take the latest record even if it is the same)
  # - we will not delete old records
  try:
    print(index_cols);
    print(cols);
    print(existing_cols);
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
      print(df.columns);
      print(df);
      merged_cols = [];
      merged_rename_cols = {};
      insert_cols = [];
      insert_rename_cols = {};
      for col in cols:
        if col not in index_cols and col not in existing_cols and col in mpdf:
          merged_cols.append(col+'_x');
          merged_rename_cols[col+'_x'] = col;
          insert_cols.append(col+'_x');
          insert_rename_cols[col+'_x'] = col;
        elif col in existing_cols:
          merged_cols.append(col+'_y');
          merged_rename_cols[col+'_y'] = col;
          insert_cols.append(col+'_x');
          insert_rename_cols[col+'_x'] = col;
        else:
          merged_cols.append(col);
          merged_rename_cols[col] = col;
          insert_cols.append(col);
          insert_rename_cols[col] = col;
      insertpdf = df[df['_merge'] == 'left_only'];
      insertpdf = insertpdf[insert_cols];
      insertpdf = insertpdf.rename(columns=insert_rename_cols);
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
  cols = ['id','name','real_name','tz','email','batch']
  index_cols = ['id']
  existing_cols = ['batch']
  print('merging user dataset');
  _merge_data(filename,index_cols,cols,existing_cols);

def merge_channeldata():
  filename = 'channel_data'
  cols = ["id","name","type","class","is_archived","is_private"]
  index_cols = ["id"]
  print('merging channel dataset');
  _merge_data(filename,index_cols,cols);

def merge_messagedata():
  #filename = 'message_data'
  filename = 'conversation_history'
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
      #message_pdf = dd_readfile(master,'message_data');
      message_pdf = dd_readfile(master,'conversation_history');
      user_pdf = dd_readfile(master,'user_data');
      thread_pdf = dd_readfile(master,'thread_data');
      # Use only subset of information (and create identical columns)
      message_part_pdf = message_pdf[['channel','type','subtype','ts','thread_ts','time','user','text']];
      if data_type == "slack":
          zone_ref_pdf = dd_readref('zone');
          country_ref_pdf = dd_readref('country');
          thread_part_pdf = thread_pdf[['channel','type','subtype','ts','thread_ts','time','user','text']];
      else:
          thread_part_pdf = pandas.DataFrame();
          # Merge message and thread data
          conversation_part_pdf = message_part_pdf.append(thread_part_pdf,ignore_index=False);
          conversation_part_pdf = conversation_part_pdf.drop_duplicates();
      if data_type == "slack":
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
      else:
          # Merge iso information with user (based upon timezone).
          # user_geo_pdf = user_pdf.merge(iso_ref_pdf,how='left',left_on='tz',right_on='TZ');
          user_geo_pdf = user_pdf;
          # Add country and city based upon user data timezone
          user_geo_pdf['ISO'] = '';
          user_geo_pdf['country'] = '';
          user_geo_pdf['city'] = '';
          # Mask NAN values of country based upon timezone information
          user_geo_pdf['COUNTRY'] = '';
          # Merge user data with conversation data based upon user id
          conversation_geo_pdf = conversation_part_pdf.merge(user_geo_pdf,how='left',left_on='user',right_on='id');
      # Add a column (replica of ts) that can be used as an number
      conversation_geo_pdf['ts_int'] = conversation_geo_pdf['ts']
      # Select columns
      conversation_pdf = conversation_geo_pdf[['channel','type','subtype','ts','thread_ts','ts_int','time','user','real_name','name','text','city','COUNTRY','ISO']];
      # Rename columns
      # remove all upper-case to allow easier postgres implementation (changed to lowercase)
      # ddpdf = conversation_pdf.rename(columns={'channel':'CHANNEL','type':'TYPE','subtype':'SUBTYPE','ts':'TS','thread_ts':'THREAD_TS','ts_int':'TS_INT','time':'TIME','user':'USER','real_name':'REAL_NAME','name':'NAME','text':'TEXT','city':'CITY','COUNTRY':'COUNTRY','ISO':'ISO'});
      ddpdf = conversation_pdf.rename(columns={'channel':'channel','type':'type','subtype':'subtype','ts':'ts','thread_ts':'thread_ts','ts_int':'ts_int','time':'time','user':'user','real_name':'real_name','name':'name','text':'text','city':'city','COUNTRY':'country','ISO':'iso'});

      dd_writefile(metrics,filename,ddpdf);
    except Exception as err:
      print('Error - create_conversationdata');
      print(err);

def create_useractivedata():
  filename = "useractive_data";
  try:
    # This requires updates to user_data to capture the batch time as the invited (also the merge to take the "original" value leaving it with the first time that user was invited)
    # Users that don't exist in conversation_data - these are users that have been invited (need to calculate the date based upon the batch to record the time of invited)
    # User's first interaction in conversation_data that is a channel join (this should also the first record sorted by TS; need to use TS from that record to record the time of joined)
    # User's first activity in conversation_data that is a message (either "null" or "channel_broadcast"; need to use TS from that record to record the time of first activity)
    # User's last activity in conversation_data that is a message (either "null" or "channel_broadcast"; need to use TS from that record to record the time of last activity)
    # User's count of activity in conversation_data that is a message (either "null" or "channel_broadcast"; need to use count(TS) from that record to record the number of activities)

    conversation_pdf = dd_readfile(metrics,'conversation_data');
    conversation_pdf = conversation_pdf.sort_values(['user','ts'],ascending=(True,True));
    user_pdf = dd_readfile(master,'user_data');
    user_pdf = user_pdf.sort_values(['id','batch'],ascending=(True,True));
    # reaction_pdf = dd_readfile(master,'reaction_data');
    # reaction_pdf = reaction_pdf.sort_values(['user','ts'],ascending=(True,True));
    ll = []
    for user in user_pdf.values.tolist():
      userconv_pdf = conversation_pdf[conversation_pdf['user'] == user[0]];
      join_date = ''
      first_message_date = ''
      last_message_date = ''
      message_count = ''
      first_reaction_date = ''
      last_reaction_date = ''
      reaction_count = ''
      if len(userconv_pdf) > 0:
        join_date = userconv_pdf['ts'].iloc[0]
        if data_type == "slack":
            u1_pdf_1 = userconv_pdf[userconv_pdf['subtype'] == 'thread_broadcast'];
            u1_pdf_2 = userconv_pdf[userconv_pdf['subtype'].isnull()];
            useract_pdf = u1_pdf_1.append(u1_pdf_2,ignore_index=False);
            useract_pdf = useract_pdf.sort_values(['user','ts'],ascending=(True,True));
        else:
            useract_pdf = userconv_pdf[userconv_pdf['subtype'] == 'default'];
        if len(useract_pdf) > 0:
          message_count = len(useract_pdf)
          first_message_date = useract_pdf['ts'].iloc[0]
          last_message_date = useract_pdf['ts'].iloc[len(useract_pdf)-1]
        if data_type == "slack":
            if float(user[5]) > float(join_date):
              invite_date = join_date
            else:
              invite_date = user[5]
      else:
        if data_type == "slack":
            invite_date = user[5]
      # userreact_pdf = reaction_pdf[reaction_pdf['user'] == user[0]];
      # if len(userreact_pdf) > 0:
      #   reaction_count = len(userreact_pdf)
      #   first_reaction_date = userreact_pdf['ts'].iloc[0]
      #   last_reaction_date = userreact_pdf['ts'].iloc[len(userreact_pdf)-1]
      if data_type == "slack":
          ll.append({'user': user[0], 'name': user[1], 'invite_date': invite_date, 'join_date': join_date, 'message_count': message_count, 'first_message_date': first_message_date, 'last_message_date': last_message_date, 'reaction_count': reaction_count, 'first_reaction_date': first_reaction_date, 'last_reaction_date': last_reaction_date})
      else:
          ll.append({'USER': user[0], 'INVITE_DATE': user[5], 'JOIN_DATE': join_date, 'MESSAGE_COUNT': message_count, 'FIRST_MESSAGE_DATE': first_message_date, 'LAST_MESSAGE_DATE': last_message_date, 'REACTION_COUNT': reaction_count, 'FIRST_REACTION_DATE': first_reaction_date, 'LAST_REACTION_DATE': last_reaction_date})

    ddpdf = pandas.DataFrame.from_records(ll);
    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error - create_useractivedata');
    print(err);

def create_nodedata():
  filename = "node_data";
  try:
    channel_pdf = dd_readfile(master,'channel_data');
    user_pdf = dd_readfile(master,'user_data');
    if data_type == "slack":
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
    else:
        user_geo_pdf['ISO'] = '';
        user_geo_pdf['country'] = '';
        user_geo_pdf['city'] = '';
        user_geo_pdf['COUNTRY'] = '';
    # Add "null" columns for union
    user_geo_pdf['type'] = 'user'
    user_geo_pdf['channel_type'] = None
    user_geo_pdf['channel_class'] = None
    if data_type == "discord":
        user_geo_pdf['name'] = user_geo_pdf['name'].mask(pandas.isnull, user_geo_pdf['real_name']);
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
    # ddpdf = ddpdf.rename(columns={'id':'ID','name':'LABEL','type':'TYPE','real_name':'NAME','ISO':'ISO','COUNTRY':'COUNTRY','city':'CITY','channel_type':'CHANNEL_TYPE','channel_class':'CHANNEL_CLASS'});
    ddpdf = ddpdf.rename(columns={'id':'id','name':'label','type':'type','real_name':'name','ISO':'iso','COUNTRY':'country','city':'city','channel_type':'channel_type','channel_class':'channel_class'});

    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error - create_nodedata');
    print(err);

def create_edgedata():
  filename = "edge_data";
  try:
    conversation_pdf = dd_readfile(metrics,'conversation_data');
    c1_pdf = conversation_pdf.copy();
    reaction_pdf = dd_readfile(master,'reaction_data');
    tag_pdf = dd_readfile(metrics,'tag_data');
    if data_type == "slack":
        c1_pdf_1 = c1_pdf[c1_pdf['subtype'] == 'thread_broadcast'];
        c1_pdf_2 = c1_pdf[c1_pdf['subtype'].isnull()];
        c1_pdf = c1_pdf_1.append(c1_pdf_2,ignore_index=False);
        c2_pdf = c1_pdf.copy();
        c2_pdf = c2_pdf[c2_pdf['thread_ts'].notnull()];
        c4_pdf = c1_pdf.merge(c2_pdf,how='left',left_on='thread_ts',right_on='ts');
        # print(c4_pdf.shape);
        c4_pdf = c4_pdf[c4_pdf['user_x'] != c4_pdf['user_y']];
        c4_pdf = c4_pdf[['channel_x','user_x','user_y']];
        c4_pdf['user_y'] = c4_pdf['user_y'].mask(pandas.isnull, c4_pdf['channel_x']);
        c4_pdf['relate'] = 'interacts';
        c4_pdf = c4_pdf.rename(columns={'channel_x':'channel','user_x':'source','user_y':'target','relate':'relate'});
        # print(c4_pdf.shape);
        c3_pdf = c1_pdf.copy();
        c5_pdf = c3_pdf.merge(reaction_pdf,how='left',left_on='ts',right_on='ts');
        c5_pdf = c5_pdf[c5_pdf['user_y'].notnull()];
        c5_pdf = c5_pdf[['channel_x','user_x','user_y']];
        c5_pdf['relate'] = 'reacts';
        c5_pdf = c5_pdf.rename(columns={'channel_x':'channel','user_x':'source','user_y':'target','relate':'relate'});
        # print(c5_pdf.shape);
        c6_pdf = c1_pdf.copy();
        c6_pdf = c6_pdf.merge(tag_pdf,how='left',on='ts');
        c6_pdf = c6_pdf[c6_pdf['user'].notnull()];
        c6_pdf = c6_pdf[c6_pdf['type_y'] == 'user'];
        c6_pdf = c6_pdf[['channel_x','user','tag']];
        c6_pdf['relate'] = 'refers';
        c6_pdf = c6_pdf.rename(columns={'channel_x':'channel','user':'source','tag':'target','relate':'relate'});
        # print(c6_pdf.shape);
        # print(c6_pdf);
        ddpdf = c4_pdf.append(c5_pdf,ignore_index=True);
        ddpdf = ddpdf.append(c6_pdf,ignore_index=True);
    else:
        c1_pdf = c1_pdf[c1_pdf['SUBTYPE'] == 'default'];
        c2_pdf = c1_pdf.copy();
        c2_pdf['TARGET'] = c2_pdf['CHANNEL'];
        c2_pdf['RELATE'] = 'teams';
        c2_pdf = c2_pdf.rename(columns={'CHANNEL':'CHANNEL','USER':'SOURCE','TARGET':'TARGET','RELATE':'RELATE'});
        c2_pdf = c2_pdf[['CHANNEL','SOURCE','TARGET','RELATE']];
        # print(c4_pdf.shape);
        c3_pdf = c1_pdf.copy();
        c4_pdf = c3_pdf.merge(c3_pdf,how='left',left_on='CHANNEL',right_on='CHANNEL');
        c4_pdf = c4_pdf[c4_pdf['USER_x'] != c4_pdf['USER_y']];
        c4_pdf = c4_pdf[['CHANNEL','USER_x','USER_y']];
        c4_pdf['RELATE'] = 'interacts';
        c4_pdf = c4_pdf.rename(columns={'CHANNEL':'CHANNEL','USER_x':'SOURCE','USER_y':'TARGET','RELATE':'RELATE'});
        c4_pdf = c4_pdf[['CHANNEL','SOURCE','TARGET','RELATE']];
        # print(c4_pdf.shape);
        c5_pdf = c1_pdf.copy();
        c6_pdf = c5_pdf.merge(reaction_pdf,how='left',left_on='TS',right_on='ts');
        c6_pdf = c6_pdf[c6_pdf['user'].notnull()];
        c6_pdf = c6_pdf[['CHANNEL','USER','user']];
        c6_pdf['RELATE'] = 'reacts';
        c6_pdf = c6_pdf.rename(columns={'CHANNEL':'CHANNEL','USER':'SOURCE','user':'TARGET','RELATE':'RELATE'});
        c6_pdf = c6_pdf[['CHANNEL','SOURCE','TARGET','RELATE']];
        # print(c5_pdf.shape);
        c7_pdf = c1_pdf.copy();
        c8_pdf = c7_pdf.merge(tag_pdf,how='left',on='TS');
        c8_pdf = c8_pdf[c8_pdf['USER'].notnull()];
        c8_pdf = c8_pdf[c8_pdf['TYPE_y'] == 'user'];
        c8_pdf = c8_pdf[['CHANNEL_x','USER','TAG']];
        c8_pdf['RELATE'] = 'refers';
        c8_pdf = c8_pdf.rename(columns={'CHANNEL_x':'CHANNEL','USER':'SOURCE','TAG':'TARGET','RELATE':'RELATE'});
        # print(c8_pdf.shape);
        # print(c8_pdf);
        ddpdf = c2_pdf.append(c4_pdf,ignore_index=True);
        ddpdf = ddpdf.append(c6_pdf,ignore_index=True);
        ddpdf = ddpdf.append(c8_pdf,ignore_index=True);

    print(ddpdf);

    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error - create_edgedata');
    print(err);

def aggregate_conversationdata():
  try:
    channel_pdf = dd_readfile(master,'channel_data');
    user_pdf = dd_readfile(master,'user_data');

    c1_pdf = dd_readfile(metrics,'conversation_data');
    if data_type == "slack":
        c1_pdf_1 = c1_pdf[c1_pdf['subtype'] == 'thread_broadcast'];
        c1_pdf_2 = c1_pdf[c1_pdf['subtype'].isnull()];
        c1_pdf = c1_pdf_1.append(c1_pdf_2,ignore_index=False);
        agg_pdf = c1_pdf.groupby('channel').count()[['ts','thread_ts']];
        # print(agg_pdf);
        dd_writefile(metrics,'aggr_by_channel',agg_pdf,True);
        agg_pdf = c1_pdf.groupby(['channel','user']).count()[['ts','thread_ts']];
    else:
        c1_pdf = c1_pdf[c1_pdf['subtype'] == 'default'];
        agg_pdf = c1_pdf.groupby('channel').count()[['ts']];
        # print(agg_pdf);
        dd_writefile(metrics,'aggr_by_channel',agg_pdf,True);
        agg_pdf = c1_pdf.groupby(['channel','user']).count()[['ts']];
    # print(agg_pdf);
    dd_writefile(metrics,'aggr_by_channel_user',agg_pdf,True);
    unique_pdf = agg_pdf.copy();
    unique_pdf.reset_index(inplace=True);
    unique_pdf = unique_pdf.groupby(['channel']).count()[['user']];
    print(unique_pdf);
    dd_writefile(metrics,'number_channel_user',unique_pdf,True);
    max_pdf = agg_pdf.groupby(['channel']).max()[['ts']];
    # print(max_pdf);
    m1_pdf = agg_pdf.merge(max_pdf,how='inner',left_index=True,right_index=True);
    m1_pdf = m1_pdf[m1_pdf['ts_x'] == m1_pdf['ts_y']];
    print(m1_pdf);
    m1_pdf.reset_index(inplace=True);
    m2_pdf = m1_pdf.merge(user_pdf,how='left',right_on='id',left_on='user');
    m3_pdf = m2_pdf.merge(channel_pdf,how='left',right_on='id',left_on='channel');
    m4_pdf = m3_pdf[['channel','name_y','user','real_name','ts_x']];
    m4_pdf = m4_pdf.rename(columns={'channel':'channel_id','name_y':'channel_name','user':'user_id','real_name':'user_name','ts_x':'ts'});
    # print(m4_pdf);
    dd_writefile(metrics,'max_by_channel_user',m4_pdf);
  except Exception as err:
    print('Error - aggregate_conversationdata');
    print(err);

def create_timediff_conversations():
  filename = "conversation_timediff_data";
  try:
    df = dd_readfile(metrics,'conversation_data');
    df = df.sort_values(['channel','ts'],ascending=(True,True));
    df['time_ts'] = pandas.to_datetime(df['time']);
    # print(df);
    ddf = df[['channel','time_ts']];
    # print(ddf);
    # print(ddf.dtypes);
    ddf = ddf.groupby('channel').diff();
    ddf['time_ts'] = ddf['time_ts'] / numpy.timedelta64(1, 's');
    ddf['time_ts'] = ddf['time_ts'].mask(pandas.isnull, 0);
    # print(ddf);
    # print(ddf.dtypes);
    df = df.merge(ddf,left_index=True,right_index=True);
    # print(df);
    # print(df.dtypes);
    # ddpdf = df[['CHANNEL','TYPE','SUBTYPE','TS','THREAD_TS','TS_INT','TIME','USER','REAL_NAME','NAME','TEXT','CITY','COUNTRY','ISO','TIME_TS_y']];
    ddpdf = df[['channel','type','subtype','ts','thread_ts','ts_int','time','user','real_name','name','text','city','country','iso','time_ts_y']];
    ddpdf = ddpdf.rename(columns={'time_ts_y':'diff'});
    # print(ddpdf);
    # print(ddpdf.dtypes);
    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error - create_timediff_conversations');
    print(err);

def create_timediff_threads():
  if data_type == "slack":
    filename = "threads_timediff_data";
    try:
      df = dd_readfile(metrics,'conversation_data');
      df = df[df['thread_ts'].notnull()];
      df = df.sort_values(['channel','thread_ts','ts'],ascending=(True,True,True));
      df['time_ts'] = pandas.to_datetime(df['time']);
      # print(df);
      ddf = df[['channel','thread_ts','time_ts']];
      # print(ddf);
      # print(ddf.dtypes);
      ddf = ddf.groupby(['channel','thread_ts']).diff();
      ddf['time_ts'] = ddf['time_ts'] / numpy.timedelta64(1, 's');
      ddf['time_ts'] = ddf['time_ts'].mask(pandas.isnull, 0);
      # print(ddf);
      # print(ddf.dtypes);
      df = df.merge(ddf,left_index=True,right_index=True);
      # print(df);
      # print(df.dtypes);
      # ddpdf = df[['CHANNEL','TYPE','SUBTYPE','TS','THREAD_TS','TS_INT','TIME','USER','REAL_NAME','NAME','TEXT','CITY','COUNTRY','ISO','TIME_TS_y']];
      ddpdf = df[['channel','type','subtype','ts','thread_ts','ts_int','time','user','real_name','name','text','city','country','iso','time_ts_y']];
      ddpdf = ddpdf.rename(columns={'time_ts_y':'diff'});
      # print(ddpdf);
      # print(ddpdf.dtypes);
      dd_writefile(metrics,filename,ddpdf);
    except Exception as err:
      print('Error - create_timediff_threads');
      print(err);

def create_timediff_users():
  filename = "users_timediff_data";
  try:
    df = dd_readfile(metrics,'conversation_data');
    if data_type == "slack":
        df = df[df['thread_ts'].notnull()];
    df = df.sort_values(['user','ts'],ascending=(True,True));
    df['user_hash'] = df['user'].apply(hash);
    df['time_ts'] = pandas.to_datetime(df['time']);
    # print(df);
    ddf = df[['user','time_ts']];
    # print(ddf);
    # print(ddf.dtypes);
    ddf = ddf.groupby(['user']).diff();
    ddf['time_ts'] = ddf['time_ts'] / numpy.timedelta64(1, 's');
    ddf['time_ts'] = ddf['time_ts'].mask(pandas.isnull, 0);
    # print(ddf);
    # print(ddf.dtypes);
    df = df.merge(ddf,left_index=True,right_index=True);
    # print(df);
    # print(df.dtypes);
    # ddpdf = df[['CHANNEL','TYPE','SUBTYPE','TS','THREAD_TS','TS_INT','TIME','USER','USER_HASH','REAL_NAME','NAME','TEXT','CITY','COUNTRY','ISO','TIME_TS_y']];
    ddpdf = df[['channel','type','subtype','ts','thread_ts','ts_int','time','user','user_hash','real_name','name','text','city','country','iso','time_ts_y']];
    ddpdf = ddpdf.rename(columns={'time_ts_y':'diff'});
    # print(ddpdf);
    # print(ddpdf.dtypes);
    dd_writefile(metrics,filename,ddpdf);
  except Exception as err:
    print('Error - create_timediff_users');
    print(err);

def aggregate_threads():
  filename = "length_threads_data";
  try:
    df = dd_readfile(metrics,'conversation_data');
    df = df[df['thread_ts'].notnull()];
    ddf = df.groupby(['channel','thread_ts']).count()[['ts']];
    ddf.reset_index(inplace=True);
    print(ddf);
    dd_writefile(metrics,'aggr_by_thread',ddf);
    ddf = df.groupby(['channel','thread_ts','user']).count()[['ts']];
    ddf.reset_index(inplace=True);
    print(ddf);
    dd_writefile(metrics,'aggr_by_thread_user',ddf);
  except Exception as err:
    print('Error - aggregate_threads');
    print(err);

def extract_tags():
    filename = "tag_data";
    try:
      df = dd_readfile(metrics,'conversation_data');
      udf = dd_readfile(master,'user_data');
      if data_type == "slack":
          df_1 = df[df['subtype'] == 'thread_broadcast'];
          df_2 = df[df['subtype'].isnull()];
          df = df_1.append(df_2,ignore_index=True);
      else:
          df = df[df['subtype'] == 'default'];
      df = df[['channel','ts','text']];
      df = df[df['text'].notnull()];
      df = df.set_index('ts');
      if data_type == "slack":
          utdf = df['text'].str.extractall(r'<@(?P<tag>.*?)>');
      else:
          utdf = df['text'].str.extractall(r'<@!(?P<tag>.*?)>');
      utdf['type'] = 'user';
      utdf.reset_index(inplace=True);
      utdf = utdf.merge(udf,how='left',left_on='tag',right_on='id');
      utdf = utdf.rename(columns={'real_name':'nice_tag'});
      utdf.reset_index(inplace=True);
      utdf = utdf[['ts','tag','nice_tag','type']];
      ctdf = df['text'].str.extractall(r'<#(?P<tag>.*?)>');
      # <#ID|NAME>
      if data_type == "slack":
          ctdf = ctdf['tag'].str.split('|', expand=True)
          ctdf['type'] = 'channel';
          ctdf = ctdf.rename(columns={0: 'tag', 1: 'nice_tag'});
      else:
          cdf = dd_readfile(master, 'channel_data');
          ctdf = ctdf.merge(cdf, how='left',left_on='tag',right_on='id')
          ctdf['type'] = 'channel';
          ctdf = ctdf.rename(columns={'name': 'nice_tag'});
          ctdf['ts'] = 0;
      ctdf.reset_index(inplace=True);
      ctdf = ctdf[['ts', 'tag', 'nice_tag', 'type']];
      if data_type == "slack":
          ltdf = df['text'].str.extractall(r'<(?P<tag>.*?)>');
          ltdf = ltdf[ltdf['tag'].str.contains('^[^@#]')];
          ltdf = ltdf['tag'].str.split('|',expand=True)
          ltdf = ltdf.rename(columns={0:'tag',1:'nice_tag'});
          ltdf['type'] = 'link';
          ltdf.reset_index(inplace=True);
          ltdf = ltdf[['ts','tag','nice_tag','type']];
      df.reset_index(inplace=True);
      print(utdf);
      print(ctdf)
      if data_type == "slack":
          print(ltdf);
          tdf = pandas.concat([utdf,ctdf,ltdf],ignore_index=True)
      else:
          tdf = pandas.concat([utdf, ctdf], ignore_index=True)
      print(tdf);
      print(df)
      ddf = df.merge(tdf,how='right',on='ts');
      ddf = ddf[['channel','ts','tag','nice_tag','type']];
      print(ddf);
      dd_writefile(metrics,filename,ddf);
    except Exception as err:
      print('Error - extract_tags');
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
      create_useractivedata();
      create_timediff_conversations();
      create_timediff_threads();
      create_timediff_users();
      extract_tags();
      #create_nodedata();
      #create_edgedata();
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

try:
  sign_token = os.environ['SLACK_SIGN_TOKEN']
  access_token = os.environ['SLACK_ACCESS_TOKEN']
  user_token = os.environ['SLACK_USER_TOKEN']
  # user_token = 'SLACK_USER_TOKEN'
  data_home = os.environ['DISCORD_DATA_HOME']
except:
  print('no tokens available')
  data_home = "."

# ssl_context = ssl.create_default_context(cafile=certifi.where())

if __name__ == "__main__":
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

  exec_stages();
