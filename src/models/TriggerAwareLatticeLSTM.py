import torch
from torch import nn
import torch.autograd as autograd
from torch.autograd import Variable
from torch.nn import functional, init
import numpy as np


class WordLSTMCell(nn.Module):
    def __init__(self, input_size, hidden_size, use_bias=True):

        super(WordLSTMCell, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.use_bias = use_bias
        self.weight_ih = nn.Parameter(
            torch.FloatTensor(input_size, 3 * hidden_size))
        self.weight_hh = nn.Parameter(
            torch.FloatTensor(hidden_size, 3 * hidden_size))
        if use_bias:
            self.bias = nn.Parameter(torch.FloatTensor(3 * hidden_size))
        else:
            self.register_parameter('bias', None)
        self.reset_parameters()

    def reset_parameters(self):

        init.orthogonal(self.weight_ih.data)
        weight_hh_data = torch.eye(self.hidden_size)
        weight_hh_data = weight_hh_data.repeat(1, 3)
        self.weight_hh.data.set_(weight_hh_data)

        if self.use_bias:
            init.constant(self.bias.data, val=0)

    def forward(self, input_, hx):


        h_0, c_0 = hx
        batch_size = h_0.size(0)
        bias_batch = (self.bias.unsqueeze(0).expand(batch_size, *self.bias.size()))
        wh_b = torch.addmm(bias_batch, h_0, self.weight_hh)
        wi = torch.mm(input_, self.weight_ih)
        f, i, g = torch.split(wh_b + wi, self.hidden_size, dim=1)
        c_1 = torch.sigmoid(f)*c_0 + torch.sigmoid(i)*torch.tanh(g)
        return c_1

    def __repr__(self):
        s = '{name}({input_size}, {hidden_size})'
        return s.format(name=self.__class__.__name__, **self.__dict__)

class SenseLSTMCell(nn.Module):


    def __init__(self, input_size, hidden_size, use_bias=True):


        super(SenseLSTMCell, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.use_bias = use_bias
        self.alpha_weight_ih = nn.Parameter(
            torch.FloatTensor(input_size, hidden_size))
        self.alpha_weight_hh = nn.Parameter(
            torch.FloatTensor(hidden_size, hidden_size))
        if use_bias:
            self.alpha_bias = nn.Parameter(torch.FloatTensor(hidden_size))
        else:
            self.register_parameter('alpha_bias', None)
        self.reset_parameters()

    def reset_parameters(self):

        init.orthogonal(self.alpha_weight_ih.data)

        alpha_weight_hh_data = torch.eye(self.hidden_size)
        alpha_weight_hh_data = alpha_weight_hh_data.repeat(1, 1)
        self.alpha_weight_hh.data.set_(alpha_weight_hh_data)


        if self.use_bias:
            init.constant(self.alpha_bias.data, val=0)

    def forward(self, input_, c_input):

        batch_size = input_.size(0)
        c_num = len(c_input)

        c_input_var = torch.cat(c_input, 0)
        alpha_bias_batch = (self.alpha_bias.unsqueeze(0).expand(batch_size, *self.alpha_bias.size()))
        c_input_var = c_input_var.squeeze(1) 
        alpha_wi = torch.addmm(self.alpha_bias, input_, self.alpha_weight_ih).expand(c_num, self.hidden_size)
        alpha_wh = torch.mm(c_input_var, self.alpha_weight_hh)
        alpha = torch.sigmoid(alpha_wi + alpha_wh)

        alpha = torch.exp(alpha)
        alpha_sum = alpha.sum(0)

        alpha = torch.div(alpha, alpha_sum)
        c_1 = c_input_var * alpha
        c_1 = c_1.sum(0).unsqueeze(0)

        return c_1

    def __repr__(self):
        s = '{name}({input_size}, {hidden_size})'
        return s.format(name=self.__class__.__name__, **self.__dict__)

class MultiInputLSTMCell(nn.Module):



    def __init__(self, input_size, hidden_size, use_bias=True):

        super(MultiInputLSTMCell, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.use_bias = use_bias
        self.weight_ih = nn.Parameter(
            torch.FloatTensor(input_size, 3 * hidden_size))
        self.weight_hh = nn.Parameter(
            torch.FloatTensor(hidden_size, 3 * hidden_size))
        self.alpha_weight_ih = nn.Parameter(
            torch.FloatTensor(input_size, hidden_size))
        self.alpha_weight_hh = nn.Parameter(
            torch.FloatTensor(hidden_size, hidden_size))
        if use_bias:
            self.bias = nn.Parameter(torch.FloatTensor(3 * hidden_size))
            self.alpha_bias = nn.Parameter(torch.FloatTensor(hidden_size))
        else:
            self.register_parameter('bias', None)
            self.register_parameter('alpha_bias', None)
        self.reset_parameters()

    def reset_parameters(self):

        init.orthogonal(self.weight_ih.data)
        init.orthogonal(self.alpha_weight_ih.data)

        weight_hh_data = torch.eye(self.hidden_size)
        weight_hh_data = weight_hh_data.repeat(1, 3)
        self.weight_hh.data.set_(weight_hh_data)

        alpha_weight_hh_data = torch.eye(self.hidden_size)
        alpha_weight_hh_data = alpha_weight_hh_data.repeat(1, 1)
        self.alpha_weight_hh.data.set_(alpha_weight_hh_data)

        if self.use_bias:
            init.constant(self.bias.data, val=0)
            init.constant(self.alpha_bias.data, val=0)

    def forward(self, input_, c_input, hx):


        h_0, c_0 = hx
        batch_size = h_0.size(0)
        assert(batch_size == 1)
        bias_batch = (self.bias.unsqueeze(0).expand(batch_size, *self.bias.size()))
        wh_b = torch.addmm(bias_batch, h_0, self.weight_hh)
        wi = torch.mm(input_, self.weight_ih)
        i, o, g = torch.split(wh_b + wi, self.hidden_size, dim=1)
        i = torch.sigmoid(i)
        g = torch.tanh(g)
        o = torch.sigmoid(o)
        c_num = len(c_input)
        if c_num == 0:
            f = 1 - i
            c_1 = f*c_0 + i*g
            h_1 = o * torch.tanh(c_1)
        else:
            c_input_var = torch.cat(c_input, 0)
            alpha_bias_batch = (self.alpha_bias.unsqueeze(0).expand(batch_size, *self.alpha_bias.size()))
            c_input_var = c_input_var.squeeze(1) 
            alpha_wi = torch.addmm(self.alpha_bias, input_, self.alpha_weight_ih).expand(c_num, self.hidden_size)
            alpha_wh = torch.mm(c_input_var, self.alpha_weight_hh)
            alpha = torch.sigmoid(alpha_wi + alpha_wh)


            alpha = torch.exp(torch.cat([i, alpha],0))
            alpha_sum = alpha.sum(0)

            alpha = torch.div(alpha, alpha_sum)
            merge_i_c = torch.cat([g, c_input_var],0)
            c_1 = merge_i_c * alpha
            c_1 = c_1.sum(0).unsqueeze(0)
            h_1 = o * torch.tanh(c_1)
        return h_1, c_1

    def __repr__(self):
        s = '{name}({input_size}, {hidden_size})'
        return s.format(name=self.__class__.__name__, **self.__dict__)


class LatticeLSTM(nn.Module):


    def __init__(self, input_dim, hidden_dim, word_drop, word_alphabet_size, word_emb_dim, pretrain_word_emb=None, left2right=True, fix_word_emb=True, gpu=True,  use_bias = True):
        super(LatticeLSTM, self).__init__()
        skip_direction = "forward" if left2right else "backward"
        print("build LatticeLSTM... ", skip_direction, ", Fix emb:", fix_word_emb, " gaz drop:", word_drop)
        self.gpu = gpu
        self.hidden_dim = hidden_dim
        self.word_emb = nn.Embedding(word_alphabet_size, word_emb_dim)
        if pretrain_word_emb is not None:
            print("load pretrain word emb...", pretrain_word_emb.shape)
            self.word_emb.weight.data.copy_(torch.from_numpy(pretrain_word_emb))

        else:

            self.word_emb.weight.data.copy_(torch.from_numpy(self.random_embedding(word_alphabet_size, word_emb_dim)))
        if fix_word_emb:
            self.word_emb.weight.requires_grad = False
        
        self.word_dropout = nn.Dropout(word_drop)

        self.rnn = MultiInputLSTMCell(input_dim, hidden_dim)
        self.sense_rnn = SenseLSTMCell(input_dim, hidden_dim)
        self.word_rnn = WordLSTMCell(word_emb_dim, hidden_dim)
        self.left2right = left2right
        if self.gpu:
            self.rnn = self.rnn.cuda()
            self.word_emb = self.word_emb.cuda()
            self.word_dropout = self.word_dropout.cuda()
            self.sense_rnn = self.sense_rnn.cuda()
            self.word_rnn = self.word_rnn.cuda()

    def random_embedding(self, vocab_size, embedding_dim):
        pretrain_emb = np.empty([vocab_size, embedding_dim])
        scale = np.sqrt(3.0 / embedding_dim)
        for index in range(vocab_size):
            pretrain_emb[index,:] = np.random.uniform(-scale, scale, [1, embedding_dim])
        return pretrain_emb

    def forward(self, input, skip_input_list, hidden=None):

        volatile_flag = skip_input_list[1]
        skip_input = skip_input_list[0]
        if not self.left2right:
            skip_input = convert_forward_gaz_to_backward(skip_input)
        input = input.transpose(1,0)
        seq_len = input.size(0)
        batch_size = input.size(1)
        assert(batch_size == 1)
        hidden_out = []
        memory_out = []
        if hidden:
            (hx,cx)= hidden
        else:
            hx = autograd.Variable(torch.zeros(batch_size, self.hidden_dim))
            cx = autograd.Variable(torch.zeros(batch_size, self.hidden_dim))
            if self.gpu:
                hx = hx.cuda()
                cx = cx.cuda()

        id_list = range(seq_len)

        if not self.left2right:
            id_list = list(reversed(id_list))
        input_c_list = init_list_of_objects(seq_len)
        for t in id_list:

            if skip_input[t]:
                
                matched_num = len(skip_input[t][0])

                word_var = autograd.Variable(torch.LongTensor(skip_input[t][0]),volatile = volatile_flag)
                if self.gpu:
                    word_var = word_var.cuda()
                word_emb = self.word_emb(word_var)
                word_emb = self.word_dropout(word_emb)
                ct = self.word_rnn(word_emb, (hx,cx))

                assert(ct.size(0)==len(skip_input[t][1]))
                sense_ct = dict() # len -> [ct,...]
                for idx in range(matched_num):
                    length = skip_input[t][1][idx]
                    if length != 1:
                        continue
                    if length not in sense_ct:
                        sense_ct[length] = [ct[idx,:].unsqueeze(0)]
                    else:
                        sense_ct[length].append(ct[idx,:].unsqueeze(0))
                for length, cts in sense_ct.items():
                    gaz_c = self.sense_rnn(input[t],cts)
                    if self.left2right:

                        input_c_list[t+length-1].append(gaz_c)
                    else:

                        input_c_list[t-length+1].append(gaz_c)

            (hx,cx) = self.rnn(input[t], input_c_list[t], (hx,cx)) # multi-input
            hidden_out.append(hx)
            memory_out.append(cx)

            if skip_input[t]:
                
                matched_num = len(skip_input[t][0])
                #print("配对数", matched_num)
                word_var = autograd.Variable(torch.LongTensor(skip_input[t][0]),volatile = volatile_flag)
                if self.gpu:
                    word_var = word_var.cuda()
                word_emb = self.word_emb(word_var)
                word_emb = self.word_dropout(word_emb)
                ct = self.word_rnn(word_emb, (hx,cx))

                assert(ct.size(0)==len(skip_input[t][1]))
                sense_ct = dict()
                for idx in range(matched_num):
                    length = skip_input[t][1][idx]
                    if length == 1:
                        continue
                    if length not in sense_ct:
                        sense_ct[length] = [ct[idx,:].unsqueeze(0)]
                    else:
                        sense_ct[length].append(ct[idx,:].unsqueeze(0))
                for length, cts in sense_ct.items():
                    gaz_c = self.sense_rnn(input[t],cts)
                    if self.left2right:
                        input_c_list[t+length-1].append(gaz_c)
                    else:

                        input_c_list[t-length+1].append(gaz_c)

        if not self.left2right:
            hidden_out = list(reversed(hidden_out))
            memory_out = list(reversed(memory_out))
        output_hidden, output_memory = torch.cat(hidden_out, 0), torch.cat(memory_out, 0)

        return output_hidden.unsqueeze(0), output_memory.unsqueeze(0)


def init_list_of_objects(size):
    list_of_objects = list()
    for i in range(0,size):
        list_of_objects.append( list() )
    return list_of_objects


def convert_forward_gaz_to_backward(forward_gaz):

    length = len(forward_gaz)
    backward_gaz = init_list_of_objects(length)
    for idx in range(length):
        if forward_gaz[idx]:
            assert(len(forward_gaz[idx])==2)
            num = len(forward_gaz[idx][0])
            for idy in range(num):
                the_id = forward_gaz[idx][0][idy]
                the_length = forward_gaz[idx][1][idy]
                new_pos = idx+the_length -1
                if backward_gaz[new_pos]:
                    backward_gaz[new_pos][0].append(the_id)
                    backward_gaz[new_pos][1].append(the_length)
                else:
                    backward_gaz[new_pos] = [[the_id],[the_length]]
    return backward_gaz


